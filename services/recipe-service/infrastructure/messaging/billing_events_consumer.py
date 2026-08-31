"""BillingEventsConsumer -- subscribes to billing-service's `billing.events`
topic exchange (routing key `billing.entitlement.*`) and dispatches
`EntitlementGranted`/`EntitlementRevoked` to their command handlers,
implementing this service's side of the `ProUpgradeEntitlementPropagation`
saga's fan-out (docs/sagas-and-distributed-transactions.md) -- the FIRST
real consumer of these two events in this codebase.

Idempotent by `event_id` via `ProcessedEntitlementEventsRepositoryPort`
(the handlers' own already-processed check is the single source of
truth). Any other billing event type (`SubscriptionStarted`/etc.) is
acknowledged and ignored -- forward-compatible, this service only cares
about the derived entitlement flag, never subscription internals.

Failure handling (messaging-conventions SKILL.md): a message that raises
is retried up to `MAX_DELIVERY_ATTEMPTS` times (a manually incremented
retry-count header, republished to the same queue and the original
ack'd), then republished to the dead-letter queue instead of being
retried forever or dropped silently. Mirrors notification-service's
`identity_events_consumer.py`/nutrition-calculation-service's
`catalog_product_consumer.py`.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

import aio_pika
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.handle_entitlement_granted import (
    HandleEntitlementGrantedCommand,
    HandleEntitlementGrantedHandler,
)
from application.commands.handle_entitlement_revoked import (
    HandleEntitlementRevokedCommand,
    HandleEntitlementRevokedHandler,
)
from infrastructure.persistence.postgres_entitlement_cache_repository import (
    PostgresEntitlementCacheRepository,
)
from infrastructure.persistence.postgres_processed_entitlement_events_repository import (
    PostgresProcessedEntitlementEventsRepository,
)

logger = structlog.get_logger()

EXCHANGE_NAME = "billing.events"
BINDING_ROUTING_KEY = "billing.entitlement.*"
QUEUE_NAME = "recipe-service.billing_entitlement_events"
DLQ_NAME = "recipe-service.billing_entitlement_events.dlq"
RETRY_HEADER = "x-recipe-service-retry-count"
MAX_DELIVERY_ATTEMPTS = 5

_HANDLED_EVENT_TYPES = {"EntitlementGranted", "EntitlementRevoked"}


async def dispatch_billing_event(
    session: AsyncSession, event_type: str, event_id: uuid.UUID, payload: dict[str, Any]
) -> None:
    """Shared dispatch helper -- used by the live consumer only today, kept
    as a standalone function (mirrors notification-service's
    `dispatch_identity_event` precedent) so any future replay tooling can
    reuse it without re-deriving the dispatch table."""
    if event_type not in _HANDLED_EVENT_TYPES:
        return

    processed_events = PostgresProcessedEntitlementEventsRepository(session)
    entitlement_cache = PostgresEntitlementCacheRepository(session)
    user_id = uuid.UUID(str(payload["user_id"]))

    if event_type == "EntitlementGranted":
        granted_handler = HandleEntitlementGrantedHandler(processed_events, entitlement_cache)
        await granted_handler.handle(
            HandleEntitlementGrantedCommand(
                event_id=event_id,
                user_id=user_id,
                granted_at=datetime.fromisoformat(payload["granted_at"]),
            )
        )
    elif event_type == "EntitlementRevoked":
        revoked_handler = HandleEntitlementRevokedHandler(processed_events, entitlement_cache)
        await revoked_handler.handle(
            HandleEntitlementRevokedCommand(
                event_id=event_id,
                user_id=user_id,
                revoked_at=datetime.fromisoformat(payload["revoked_at"]),
            )
        )


class BillingEventsConsumer:
    def __init__(
        self, session_factory: Callable[[], AsyncSession], max_attempts: int = MAX_DELIVERY_ATTEMPTS
    ) -> None:
        self._session_factory = session_factory
        self._max_attempts = max_attempts
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._queue: aio_pika.abc.AbstractQueue | None = None

    async def setup(
        self, connection: aio_pika.abc.AbstractRobustConnection
    ) -> aio_pika.abc.AbstractQueue:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=20)
        exchange = await channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        await channel.declare_queue(DLQ_NAME, durable=True)
        queue = await channel.declare_queue(QUEUE_NAME, durable=True)
        await queue.bind(exchange, routing_key=BINDING_ROUTING_KEY)

        self._channel = channel
        self._queue = queue
        return queue

    async def consume(self) -> None:
        assert self._queue is not None, "call setup() first"
        await self._queue.consume(self.on_message, no_ack=False)

    async def on_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        try:
            await self.process_body(json.loads(message.body.decode("utf-8")))
            await message.ack()
        except Exception:
            logger.exception("billing_event_processing_failed", message_id=message.message_id)
            await self._retry_or_dead_letter(message)

    async def process_body(self, body: dict[str, Any]) -> None:
        """Public so integration tests can exercise processing without a
        real broker connection."""
        event_type = body["event_type"]
        event_id = uuid.UUID(body["event_id"])
        payload = body["payload"]

        async with self._session_factory() as session:
            await dispatch_billing_event(session, event_type, event_id, payload)
            await session.commit()

    async def _retry_or_dead_letter(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        assert self._channel is not None
        headers = dict(message.headers or {})
        attempt = int(headers.get(RETRY_HEADER, 0)) + 1  # type: ignore[arg-type]

        if attempt > self._max_attempts:
            target_queue_name = DLQ_NAME
            logger.error(
                "billing_event_dead_lettered", message_id=message.message_id, attempts=attempt
            )
        else:
            target_queue_name = QUEUE_NAME
            headers[RETRY_HEADER] = attempt

        await self._channel.default_exchange.publish(
            aio_pika.Message(
                body=message.body,
                headers=headers,
                content_type=message.content_type,
                message_id=message.message_id,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=target_queue_name,
        )
        await message.ack()
