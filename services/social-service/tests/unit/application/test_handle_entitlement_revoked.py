"""HandleEntitlementRevokedHandler -- unit tests against fake ports
(hexagonal-architecture SKILL.md), plus the structural guard proving
revocation can never touch `FollowRepositoryPort`. The idempotency case
is parametrized over how many times the SAME event is replayed (see
test_handle_entitlement_granted.py's identical rationale)."""

from __future__ import annotations

import inspect
import uuid
from datetime import datetime, timezone

import pytest

from application.commands.handle_entitlement_revoked import (
    HandleEntitlementRevokedCommand,
    HandleEntitlementRevokedHandler,
)
from tests.fixtures.factories import (
    FakeEntitlementCacheRepository,
    FakeProcessedEntitlementEventsRepository,
)

REVOKED_AT = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _build_handler(
    seed: dict[uuid.UUID, bool] | None = None,
) -> tuple[
    HandleEntitlementRevokedHandler,
    FakeEntitlementCacheRepository,
    FakeProcessedEntitlementEventsRepository,
]:
    cache = FakeEntitlementCacheRepository(seed=seed)
    processed = FakeProcessedEntitlementEventsRepository()
    return HandleEntitlementRevokedHandler(processed, cache), cache, processed


async def test_valid_event_upserts_cache_entitled_false_and_marks_processed():
    handler, cache, processed = _build_handler(seed={})
    user_id, event_id = uuid.uuid4(), uuid.uuid4()

    await handler.handle(
        HandleEntitlementRevokedCommand(event_id=event_id, user_id=user_id, revoked_at=REVOKED_AT)
    )

    assert cache.by_user[user_id] is False
    assert await processed.is_processed(event_id) is True


@pytest.mark.parametrize("delivery_count", [1, 2, 5])
async def test_replaying_the_same_event_id_writes_cache_at_most_once(delivery_count: int):
    handler, cache, _processed = _build_handler(seed={uuid.uuid4(): True})
    user_id, event_id = uuid.uuid4(), uuid.uuid4()
    command = HandleEntitlementRevokedCommand(
        event_id=event_id, user_id=user_id, revoked_at=REVOKED_AT
    )

    for _ in range(delivery_count):
        await handler.handle(command)

    assert cache.upsert_calls == 1


def test_handler_never_references_follow_repository_port():
    """Structural guard (implementation plan section 1.2): revocation is
    non-destructive -- this handler's constructor has no parameter for a
    FollowRepositoryPort at all, so it is structurally impossible for it
    to delete/hide any existing follow."""
    signature = inspect.signature(HandleEntitlementRevokedHandler.__init__)
    param_names = set(signature.parameters.keys())
    assert not any("follow" in name.lower() for name in param_names if name != "self")
