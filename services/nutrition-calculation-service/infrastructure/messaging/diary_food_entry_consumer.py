"""RabbitMqDiaryFoodEntryConsumer -- this service's first live inbound
dependency on diary-service's event stream (implementation plan section 1,
acceptance criterion 3). Consumes diary-service's `diary.events` topic
exchange, routing key `diary.food_entry.*` (`FoodEntryLogged`/
`FoodEntryCorrected`/`FoodEntryDeleted`), and triggers
`RecomputeDailyNutrientTotalHandler`.

Idempotent by `(consumer_name, event_id)` (messaging-conventions
SKILL.md) via `ProcessedEventsPort` -- enforced here, before the handler
runs, so redelivery after a crash mid-processing is always safe; the
underlying entity's upsert-by-`entry_id` is a second, independent
backstop (implementation plan acceptance criterion 4).

`FoodEntryDeleted`'s payload carries no date (`{entry_id, user_id,
deleted_at}`, docs/events-catalog.md) -- this consumer resolves the
`total_date` to operate on via
`DailyNutritionTotalRepositoryPort.find_date_for_entry` before invoking
the handler; if no day is found (already removed, or never recorded here)
the delete is a safe no-op, still marked processed.

Failure handling (messaging-conventions SKILL.md): a message that raises
is retried up to MAX_DELIVERY_ATTEMPTS times (a manually incremented
`x-nutrition-calc-retry-count` header, republished to the same queue and
the original ack'd), then republished to the dead-letter queue instead of
being retried forever or dropped silently.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

import aio_pika
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.recompute_daily_nutrient_total import (
    RecomputeDailyNutrientTotalCommand,
    RecomputeDailyNutrientTotalHandler,
)
from infrastructure.caching.redis_current_total_cache import RedisCurrentTotalCache
from infrastructure.persistence.postgres_daily_nutrition_total_repository import (
    PostgresDailyNutritionTotalRepository,
)
from infrastructure.persistence.postgres_nutrient_panel_mirror_repository import (
    PostgresNutrientPanelMirrorRepository,
)
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from infrastructure.persistence.postgres_processed_events_repository import (
    PostgresProcessedEventsRepository,
)

logger = structlog.get_logger()

EXCHANGE_NAME = "diary.events"
BINDING_ROUTING_KEY = "diary.food_entry.*"
QUEUE_NAME = "nutrition-calculation-service.diary_food_entry"
DLQ_NAME = "nutrition-calculation-service.diary_food_entry.dlq"
RETRY_HEADER = "x-nutrition-calc-retry-count"
MAX_DELIVERY_ATTEMPTS = 5
CONSUMER_NAME = "diary_food_entry"

_RECOMPUTE_EVENT_TYPES = {"FoodEntryLogged", "FoodEntryCorrected", "FoodEntryDeleted"}


class DiaryFoodEntryConsumer:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        redis_cache: RedisCurrentTotalCache | None = None,
        max_attempts: int = MAX_DELIVERY_ATTEMPTS,
    ) -> None:
        self._session_factory = session_factory
        self._redis_cache = redis_cache
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
            logger.exception("diary_food_entry_processing_failed", message_id=message.message_id)
            await self._retry_or_dead_letter(message)

    async def process_body(self, body: dict[str, Any]) -> None:
        """Public so integration tests can exercise processing without a
        real broker connection -- same pattern diary-service's own
        consumer tests use."""
        event_type = body["event_type"]
        if event_type not in _RECOMPUTE_EVENT_TYPES:
            return

        event_id = uuid.UUID(body["event_id"])
        payload = body["payload"]
        user_id = uuid.UUID(payload["user_id"])
        entry_id = uuid.UUID(payload["entry_id"])
        correlation_id = body["metadata"]["correlation_id"]

        async with self._session_factory() as session:
            processed_events = PostgresProcessedEventsRepository(session)
            if await processed_events.already_processed(CONSUMER_NAME, event_id):
                return

            totals_repository = PostgresDailyNutritionTotalRepository(session)
            resolved_total_date: date

            if event_type == "FoodEntryDeleted":
                found_date = await totals_repository.find_date_for_entry(user_id, entry_id)
                if found_date is None:
                    await processed_events.mark_processed(CONSUMER_NAME, event_id)
                    await session.commit()
                    return
                resolved_total_date = found_date
                command = RecomputeDailyNutrientTotalCommand(
                    user_id=user_id,
                    entry_id=entry_id,
                    total_date=resolved_total_date,
                    trigger_event_type=event_type,
                    correlation_id=correlation_id,
                )
            else:
                source = payload["source"]
                snapshot = source["snapshot"]
                occurred_at = datetime.fromisoformat(payload["occurred_at"])
                resolved_total_date = occurred_at.date()
                command = RecomputeDailyNutrientTotalCommand(
                    user_id=user_id,
                    entry_id=entry_id,
                    total_date=resolved_total_date,
                    trigger_event_type=event_type,
                    correlation_id=correlation_id,
                    quantity_grams=snapshot["quantity"],
                    macros_per_unit=snapshot["macros_per_unit"],
                    source_type=source["source_type"],
                    source_reference_id=source.get("source_reference_id"),
                )

            mirror_port = PostgresNutrientPanelMirrorRepository(session)
            outbox = PostgresOutboxRepository(session)
            handler = RecomputeDailyNutrientTotalHandler(totals_repository, mirror_port, outbox)
            await handler.handle(command)
            await processed_events.mark_processed(CONSUMER_NAME, event_id)
            await session.commit()

        if self._redis_cache is not None:
            await self._redis_cache.invalidate(user_id, resolved_total_date)

    async def _retry_or_dead_letter(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        assert self._channel is not None
        headers = dict(message.headers or {})
        attempt = int(headers.get(RETRY_HEADER, 0)) + 1  # type: ignore[arg-type]

        if attempt > self._max_attempts:
            target_queue_name = DLQ_NAME
            logger.error(
                "diary_food_entry_dead_lettered", message_id=message.message_id, attempts=attempt
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
