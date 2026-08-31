from __future__ import annotations

import uuid
from datetime import datetime, timezone

from application.commands.handle_entitlement_revoked import (
    HandleEntitlementRevokedCommand,
    HandleEntitlementRevokedHandler,
)
from tests.fixtures.factories import (
    FakeEntitlementCacheRepository,
    FakeProcessedEntitlementEventsRepository,
)

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


async def test_valid_event_upserts_cache_entitled_false_and_marks_processed():
    cache = FakeEntitlementCacheRepository(seed={})
    processed = FakeProcessedEntitlementEventsRepository()
    handler = HandleEntitlementRevokedHandler(processed, cache)
    user_id = uuid.uuid4()
    event_id = uuid.uuid4()

    await handler.handle(
        HandleEntitlementRevokedCommand(event_id=event_id, user_id=user_id, revoked_at=NOW)
    )

    assert cache.by_user[user_id] is False
    assert await processed.is_processed(event_id) is True


async def test_same_event_id_processed_twice_writes_cache_exactly_once():
    cache = FakeEntitlementCacheRepository(seed={uuid.uuid4(): True})
    processed = FakeProcessedEntitlementEventsRepository()
    handler = HandleEntitlementRevokedHandler(processed, cache)
    user_id = uuid.uuid4()
    event_id = uuid.uuid4()
    command = HandleEntitlementRevokedCommand(event_id=event_id, user_id=user_id, revoked_at=NOW)

    await handler.handle(command)
    await handler.handle(command)

    assert cache.upsert_calls == 1
