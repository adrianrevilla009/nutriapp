from __future__ import annotations

import uuid
from datetime import datetime, timezone

from application.commands.handle_entitlement_granted import (
    HandleEntitlementGrantedCommand,
    HandleEntitlementGrantedHandler,
)
from tests.fixtures.factories import (
    FakeEntitlementCacheRepository,
    FakeProcessedEntitlementEventsRepository,
)

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


async def test_valid_event_upserts_cache_entitled_true_and_marks_processed():
    cache = FakeEntitlementCacheRepository()
    processed = FakeProcessedEntitlementEventsRepository()
    handler = HandleEntitlementGrantedHandler(processed, cache)
    user_id = uuid.uuid4()
    event_id = uuid.uuid4()

    await handler.handle(
        HandleEntitlementGrantedCommand(event_id=event_id, user_id=user_id, granted_at=NOW)
    )

    assert cache.by_user[user_id] is True
    assert await processed.is_processed(event_id) is True


async def test_same_event_id_processed_twice_writes_cache_exactly_once():
    cache = FakeEntitlementCacheRepository()
    processed = FakeProcessedEntitlementEventsRepository()
    handler = HandleEntitlementGrantedHandler(processed, cache)
    user_id = uuid.uuid4()
    event_id = uuid.uuid4()
    command = HandleEntitlementGrantedCommand(event_id=event_id, user_id=user_id, granted_at=NOW)

    await handler.handle(command)
    await handler.handle(command)

    assert cache.upsert_calls == 1
