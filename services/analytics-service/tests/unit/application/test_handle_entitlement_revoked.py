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


async def test_valid_event_upserts_cache_entitled_false():
    processed = FakeProcessedEntitlementEventsRepository()
    cache = FakeEntitlementCacheRepository(seed={})
    user_id = uuid.uuid4()
    cache.by_user[user_id] = True
    handler = HandleEntitlementRevokedHandler(processed, cache)

    await handler.handle(
        HandleEntitlementRevokedCommand(
            event_id=uuid.uuid4(), user_id=user_id, revoked_at=datetime.now(timezone.utc)
        )
    )

    assert cache.by_user[user_id] is False


async def test_revocation_never_touches_any_other_repository():
    # Structural guard: the handler's constructor only accepts
    # processed-events + entitlement-cache ports -- it has no way to
    # reach daily_log_summary/micronutrient_window/anomaly_alerts at all.
    import inspect

    signature = inspect.signature(HandleEntitlementRevokedHandler.__init__)
    assert set(signature.parameters) == {"self", "processed_events", "entitlement_cache"}


async def test_redelivered_event_id_upserts_cache_exactly_once():
    processed = FakeProcessedEntitlementEventsRepository()
    cache = FakeEntitlementCacheRepository()
    command = HandleEntitlementRevokedCommand(
        event_id=uuid.uuid4(), user_id=uuid.uuid4(), revoked_at=datetime.now(timezone.utc)
    )
    handler = HandleEntitlementRevokedHandler(processed, cache)

    await handler.handle(command)
    await handler.handle(command)

    assert cache.upsert_calls == 1
