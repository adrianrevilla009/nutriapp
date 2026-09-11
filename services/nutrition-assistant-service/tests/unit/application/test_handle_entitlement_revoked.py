from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime

from application.commands.handle_entitlement_revoked import (
    HandleEntitlementRevokedCommand,
    HandleEntitlementRevokedHandler,
)
from tests.fixtures.fakes import FakeEntitlementCacheRepository, FakeProcessedEventsRepository


async def test_valid_event_upserts_cache_entitled_false() -> None:
    processed = FakeProcessedEventsRepository()
    user_id = uuid.uuid4()
    cache = FakeEntitlementCacheRepository(cached={user_id: True})
    handler = HandleEntitlementRevokedHandler(processed, cache)

    await handler.handle(
        HandleEntitlementRevokedCommand(
            event_id=uuid.uuid4(), user_id=user_id, revoked_at=datetime.now(UTC)
        )
    )

    assert (await cache.get(user_id)) is False


async def test_upsert_uses_the_events_own_revoked_at_timestamp() -> None:
    processed = FakeProcessedEventsRepository()
    cache = FakeEntitlementCacheRepository()
    user_id = uuid.uuid4()
    revoked_at = datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC)
    handler = HandleEntitlementRevokedHandler(processed, cache)

    await handler.handle(
        HandleEntitlementRevokedCommand(
            event_id=uuid.uuid4(), user_id=user_id, revoked_at=revoked_at
        )
    )

    assert cache.upsert_calls == [(user_id, False, revoked_at)]


def test_revocation_never_touches_any_other_repository() -> None:
    # Structural guard: the handler's constructor only accepts
    # processed-events + entitlement-cache ports -- it has no way to reach
    # diary_history/nutrition_history/analytics_signals at all.
    signature = inspect.signature(HandleEntitlementRevokedHandler.__init__)
    assert set(signature.parameters) == {"self", "processed_events", "entitlement_cache"}


async def test_redelivered_event_id_upserts_cache_exactly_once() -> None:
    processed = FakeProcessedEventsRepository()
    cache = FakeEntitlementCacheRepository()
    command = HandleEntitlementRevokedCommand(
        event_id=uuid.uuid4(), user_id=uuid.uuid4(), revoked_at=datetime.now(UTC)
    )
    handler = HandleEntitlementRevokedHandler(processed, cache)

    await handler.handle(command)
    await handler.handle(command)

    assert len(cache.upsert_calls) == 1
