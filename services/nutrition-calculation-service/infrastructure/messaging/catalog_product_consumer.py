"""RabbitMqCatalogProductConsumer -- builds this service's local,
read-only mirror of catalog-service's nutrient panel (implementation plan
section 6(c)). Consumes catalog-service's `catalog.events` topic exchange,
routing key `catalog.product.*` (`ProductCatalogued`/`ProductUpdated`),
and upserts `nutrient_panel_mirror` keyed by `product_id`.

Idempotent by `(consumer_name, event_id)` via `ProcessedEventsPort` --
test-plan section 2's idempotency case. The mirror itself is also
naturally idempotent to replay (an upsert by `source_reference_id`, never
an append) -- a second, independent backstop.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any

import aio_pika
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.upsert_nutrient_panel_mirror_entry import (
    UpsertNutrientPanelMirrorEntryCommand,
    UpsertNutrientPanelMirrorEntryHandler,
)
from infrastructure.persistence.postgres_nutrient_panel_mirror_repository import (
    PostgresNutrientPanelMirrorRepository,
)
from infrastructure.persistence.postgres_processed_events_repository import (
    PostgresProcessedEventsRepository,
)

logger = structlog.get_logger()

EXCHANGE_NAME = "catalog.events"
BINDING_ROUTING_KEY = "catalog.product.*"
QUEUE_NAME = "nutrition-calculation-service.catalog_product"
DLQ_NAME = "nutrition-calculation-service.catalog_product.dlq"
RETRY_HEADER = "x-nutrition-calc-retry-count"
MAX_DELIVERY_ATTEMPTS = 5
CONSUMER_NAME = "catalog_product"

_MIRROR_EVENT_TYPES = {"ProductCatalogued", "ProductUpdated"}


class CatalogProductConsumer:
    def __init__(
        self, session_factory: Callable[[], AsyncSession], max_attempts: int = MAX_DELIVERY_ATTEMPTS
    ) -> None:
        self._session_factory = session_factory
        self._max_attempts = max_attempts
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._queue: aio_pika.abc.AbstractQueue | None = None
        self._dlq: aio_pika.abc.AbstractQueue | None = None

    async def setup(
        self, connection: aio_pika.abc.AbstractRobustConnection
    ) -> aio_pika.abc.AbstractQueue:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=20)
        exchange = await channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        dlq = await channel.declare_queue(DLQ_NAME, durable=True)
        queue = await channel.declare_queue(QUEUE_NAME, durable=True)
        await queue.bind(exchange, routing_key=BINDING_ROUTING_KEY)

        self._channel = channel
        self._queue = queue
        self._dlq = dlq
        return queue

    async def consume(self) -> None:
        assert self._queue is not None, "call setup() first"
        await self._queue.consume(self.on_message, no_ack=False)

    async def on_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        try:
            await self.process_body(json.loads(message.body.decode("utf-8")))
            await message.ack()
        except Exception:
            logger.exception("catalog_product_processing_failed", message_id=message.message_id)
            await self._retry_or_dead_letter(message)

    async def process_body(self, body: dict[str, Any]) -> None:
        """Public so integration tests can exercise processing without a
        real broker connection."""
        event_type = body["event_type"]
        if event_type not in _MIRROR_EVENT_TYPES:
            return

        event_id = uuid.UUID(body["event_id"])
        payload = body["payload"]

        async with self._session_factory() as session:
            processed_events = PostgresProcessedEventsRepository(session)
            if await processed_events.already_processed(CONSUMER_NAME, event_id):
                return

            mirror_port = PostgresNutrientPanelMirrorRepository(session)
            handler = UpsertNutrientPanelMirrorEntryHandler(mirror_port)
            command = UpsertNutrientPanelMirrorEntryCommand(
                source_reference_id=str(payload["product_id"]),
                nutrition_per_100g=payload.get("nutrition_per_100g"),
            )
            await handler.handle(command)
            await processed_events.mark_processed(CONSUMER_NAME, event_id)
            await session.commit()

    async def _retry_or_dead_letter(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        assert self._channel is not None
        headers = dict(message.headers or {})
        attempt = int(headers.get(RETRY_HEADER, 0)) + 1  # type: ignore[arg-type]

        if attempt > self._max_attempts:
            target_queue_name = DLQ_NAME
            logger.error(
                "catalog_product_dead_lettered", message_id=message.message_id, attempts=attempt
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
