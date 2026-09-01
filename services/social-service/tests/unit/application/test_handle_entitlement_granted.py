"""HandleEntitlementGrantedHandler -- unit tests against fake ports
(hexagonal-architecture SKILL.md). The idempotency case is parametrized
over how many times the SAME event is replayed, rather than hard-coding
"exactly twice", so the property under test is genuinely "at most one
cache write no matter how many redeliveries" (test-plan section 1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from application.commands.handle_entitlement_granted import (
    HandleEntitlementGrantedCommand,
    HandleEntitlementGrantedHandler,
)
from tests.fixtures.factories import (
    FakeEntitlementCacheRepository,
    FakeProcessedEntitlementEventsRepository,
)

GRANTED_AT = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _build_handler() -> tuple[
    HandleEntitlementGrantedHandler,
    FakeEntitlementCacheRepository,
    FakeProcessedEntitlementEventsRepository,
]:
    cache = FakeEntitlementCacheRepository()
    processed = FakeProcessedEntitlementEventsRepository()
    return HandleEntitlementGrantedHandler(processed, cache), cache, processed


async def test_valid_event_upserts_cache_entitled_true_and_marks_processed():
    handler, cache, processed = _build_handler()
    user_id, event_id = uuid.uuid4(), uuid.uuid4()

    await handler.handle(
        HandleEntitlementGrantedCommand(event_id=event_id, user_id=user_id, granted_at=GRANTED_AT)
    )

    assert cache.by_user[user_id] is True
    assert await processed.is_processed(event_id) is True


@pytest.mark.parametrize("delivery_count", [1, 2, 5])
async def test_replaying_the_same_event_id_writes_cache_at_most_once(delivery_count: int):
    handler, cache, _processed = _build_handler()
    user_id, event_id = uuid.uuid4(), uuid.uuid4()
    command = HandleEntitlementGrantedCommand(
        event_id=event_id, user_id=user_id, granted_at=GRANTED_AT
    )

    for _ in range(delivery_count):
        await handler.handle(command)

    assert cache.upsert_calls == 1
