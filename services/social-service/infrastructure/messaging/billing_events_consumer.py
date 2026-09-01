"""BillingEventsConsumer -- subscribes to billing-service's `billing.events`
topic exchange (routing key `billing.entitlement.*`) and dispatches
`EntitlementGranted`/`EntitlementRevoked` to their command handlers,
implementing this service's side of the `ProUpgradeEntitlementPropagation`
saga's fan-out (docs/sagas-and-distributed-transactions.md) --
social-service is the SECOND real consumer of these two events
(recipe-service was the first).

Idempotent by `event_id` via `ProcessedEntitlementEventsRepositoryPort`
(the handlers' own already-processed check is the single source of
truth). Any other billing event type (`SubscriptionStarted`/etc.) is
acknowledged and ignored -- forward-compatible, this service only cares
about the derived entitlement flag, never subscription internals.

The retry-then-dead-letter mechanics themselves live in
`resilient_topic_consumer.py`, shared with this service's other consumer
(`recipe_events_consumer.py`) -- this module supplies only the queue
topology and the entitlement-specific dispatch."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.handle_entitlement_granted import (
    HandleEntitlementGrantedCommand,
    HandleEntitlementGrantedHandler,
)
from application.commands.handle_entitlement_revoked import (
    HandleEntitlementRevokedCommand,
    HandleEntitlementRevokedHandler,
)
from infrastructure.messaging.resilient_topic_consumer import ResilientTopicConsumer
from infrastructure.persistence.postgres_entitlement_cache_repository import (
    PostgresEntitlementCacheRepository,
)
from infrastructure.persistence.postgres_processed_entitlement_events_repository import (
    PostgresProcessedEntitlementEventsRepository,
)

EXCHANGE_NAME = "billing.events"
BINDING_ROUTING_KEY = "billing.entitlement.*"
QUEUE_NAME = "social-service.billing_entitlement_events"
DLQ_NAME = "social-service.billing_entitlement_events.dlq"
RETRY_HEADER = "x-social-service-retry-count"

_HANDLED_EVENT_TYPES = frozenset({"EntitlementGranted", "EntitlementRevoked"})


async def dispatch_billing_event(
    session: AsyncSession, event_type: str, event_id: uuid.UUID, payload: dict[str, Any]
) -> None:
    """Standalone on purpose (not a method) so any future replay tooling
    can re-apply a stored billing event without going through a live
    consumer instance at all."""
    if event_type not in _HANDLED_EVENT_TYPES:
        return

    processed_events = PostgresProcessedEntitlementEventsRepository(session)
    entitlement_cache = PostgresEntitlementCacheRepository(session)
    user_id = uuid.UUID(str(payload["user_id"]))

    if event_type == "EntitlementGranted":
        await HandleEntitlementGrantedHandler(processed_events, entitlement_cache).handle(
            HandleEntitlementGrantedCommand(
                event_id=event_id,
                user_id=user_id,
                granted_at=datetime.fromisoformat(payload["granted_at"]),
            )
        )
    else:
        await HandleEntitlementRevokedHandler(processed_events, entitlement_cache).handle(
            HandleEntitlementRevokedCommand(
                event_id=event_id,
                user_id=user_id,
                revoked_at=datetime.fromisoformat(payload["revoked_at"]),
            )
        )


class BillingEventsConsumer(ResilientTopicConsumer):
    exchange_name = EXCHANGE_NAME
    binding_routing_key = BINDING_ROUTING_KEY
    queue_name = QUEUE_NAME
    dlq_name = DLQ_NAME
    retry_header = RETRY_HEADER
    processing_failed_log_event = "billing_event_processing_failed"
    dead_lettered_log_event = "billing_event_dead_lettered"

    async def dispatch(
        self, session: AsyncSession, event_type: str, event_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        await dispatch_billing_event(session, event_type, event_id, payload)
