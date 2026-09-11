from __future__ import annotations

import uuid
from datetime import UTC, datetime

from application.commands.handle_entitlement_granted import (
    HandleEntitlementGrantedCommand,
    HandleEntitlementGrantedHandler,
)
from tests.fixtures.fakes import FakeEntitlementCacheRepository, FakeProcessedEventsRepository


async def test_valid_event_upserts_cache_entitled_true() -> None:
    processed = FakeProcessedEventsRepository()
    cache = FakeEntitlementCacheRepository()
    user_id = uuid.uuid4()
    handler = HandleEntitlementGrantedHandler(processed, cache)

    await handler.handle(
        HandleEntitlementGrantedCommand(
            event_id=uuid.uuid4(), user_id=user_id, granted_at=datetime.now(UTC)
        )
    )

    assert (await cache.get(user_id)) is True


async def test_upsert_uses_the_events_own_granted_at_timestamp() -> None:
    processed = FakeProcessedEventsRepository()
    cache = FakeEntitlementCacheRepository()
    user_id = uuid.uuid4()
    granted_at = datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC)
    handler = HandleEntitlementGrantedHandler(processed, cache)

    await handler.handle(
        HandleEntitlementGrantedCommand(
            event_id=uuid.uuid4(), user_id=user_id, granted_at=granted_at
        )
    )

    assert cache.upsert_calls == [(user_id, True, granted_at)]


async def test_redelivered_event_id_upserts_cache_exactly_once() -> None:
    processed = FakeProcessedEventsRepository()
    cache = FakeEntitlementCacheRepository()
    command = HandleEntitlementGrantedCommand(
        event_id=uuid.uuid4(), user_id=uuid.uuid4(), granted_at=datetime.now(UTC)
    )
    handler = HandleEntitlementGrantedHandler(processed, cache)

    await handler.handle(command)
    await handler.handle(command)

    assert len(cache.upsert_calls) == 1
