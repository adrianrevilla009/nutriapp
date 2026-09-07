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


async def test_valid_event_upserts_cache_entitled_true():
    processed = FakeProcessedEntitlementEventsRepository()
    cache = FakeEntitlementCacheRepository()
    user_id = uuid.uuid4()
    handler = HandleEntitlementGrantedHandler(processed, cache)

    await handler.handle(
        HandleEntitlementGrantedCommand(
            event_id=uuid.uuid4(), user_id=user_id, granted_at=datetime.now(timezone.utc)
        )
    )

    assert cache.by_user[user_id] is True


async def test_redelivered_event_id_upserts_cache_exactly_once():
    processed = FakeProcessedEntitlementEventsRepository()
    cache = FakeEntitlementCacheRepository()
    command = HandleEntitlementGrantedCommand(
        event_id=uuid.uuid4(), user_id=uuid.uuid4(), granted_at=datetime.now(timezone.utc)
    )
    handler = HandleEntitlementGrantedHandler(processed, cache)

    await handler.handle(command)
    await handler.handle(command)

    assert cache.upsert_calls == 1
