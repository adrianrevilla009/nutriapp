"""DiaryEventProjectorConsumer -- the async projector-via-broker consumer
(implementation plan section 9.1's resolved decision). Subscribes to this
service's OWN `diary.events` topic exchange (routing key `diary.#`,
catching all 10 event types this service publishes) and dispatches each
event, by event_type, to the relevant projector(s) -- one event can feed
more than one read model, e.g. FoodEntryLogged -> food_entries_view AND
daily_summary_view.

Idempotent by event_id (messaging-conventions SKILL.md) via
ProcessedEventsPort -- the mandatory idempotency test for this service's
first *new* consumer (test-plan section 2/5, acceptance criterion 8):
redelivering the same event must not double-apply it.

Failure handling (messaging-conventions SKILL.md): a message that raises
is retried up to MAX_DELIVERY_ATTEMPTS times (a manually incremented
`x-diary-retry-count` header, republished to the same queue and the
original ack'd -- classic queues do not expose a native per-message
delivery counter), then republished to the dead-letter queue instead of
being retried forever or dropped silently.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any

import aio_pika
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from domain.events.base import DomainEvent, EventMetadata
from infrastructure.cache.redis_daily_summary_cache import RedisDailySummaryCache
from infrastructure.persistence.postgres_processed_events_repository import (
    PostgresProcessedEventsRepository,
)
from infrastructure.persistence.projectors.daily_summary_projector import (
    PostgresDailySummaryProjector,
)
from infrastructure.persistence.projectors.fasting_windows_projector import (
    PostgresFastingWindowsProjector,
)
from infrastructure.persistence.projectors.food_entries_projector import (
    PostgresFoodEntriesProjector,
)
from infrastructure.persistence.projectors.meal_plan_projector import PostgresMealPlanProjector
from infrastructure.persistence.projectors.water_intake_projector import (
    PostgresWaterIntakeProjector,
)

logger = structlog.get_logger()

EXCHANGE_NAME = "diary.events"
BINDING_ROUTING_KEY = "diary.#"
QUEUE_NAME = "diary-service.diary_event_projector"
DLQ_NAME = "diary-service.diary_event_projector.dlq"
RETRY_HEADER = "x-diary-retry-count"
MAX_DELIVERY_ATTEMPTS = 5

_ENTITY_PROJECTOR_BY_EVENT_TYPE = {
    "FoodEntryLogged": "food",
    "FoodEntryCorrected": "food",
    "FoodEntryDeleted": "food",
    "WaterIntakeLogged": "water",
    "WaterIntakeRemoved": "water",
    "FastingWindowStarted": "fasting",
    "FastingWindowEnded": "fasting",
    "MealPlanned": "meal_plan",
    "MealPlanUpdated": "meal_plan",
    "MealPlanRemoved": "meal_plan",
}


def _event_from_wire(body: dict[str, Any]) -> DomainEvent:
    metadata = body["metadata"]
    return DomainEvent(
        event_id=uuid.UUID(body["event_id"]),
        event_type=body["event_type"],
        version=body["version"],
        aggregate_id=body["aggregate_id"],
        payload=body["payload"],
        metadata=EventMetadata(
            correlation_id=metadata["correlation_id"],
            causation_id=metadata.get("causation_id"),
            user_id=metadata.get("user_id"),
        ),
    )


async def apply_event_to_read_models(
    session: AsyncSession, event: DomainEvent, redis_cache: RedisDailySummaryCache | None
) -> None:
    """Dispatches one event to its entity-specific projector, then to the
    daily summary projector (which recomputes from the entity projectors'
    now-updated state) -- shared by both the live consumer and
    scripts/rebuild_read_models.py so both paths apply events identically."""
    entity = _ENTITY_PROJECTOR_BY_EVENT_TYPE.get(event.event_type)
    if entity == "food":
        await PostgresFoodEntriesProjector(session).apply(event)
    elif entity == "water":
        await PostgresWaterIntakeProjector(session).apply(event)
    elif entity == "fasting":
        await PostgresFastingWindowsProjector(session).apply(event)
    elif entity == "meal_plan":
        await PostgresMealPlanProjector(session).apply(event)

    daily_summary = PostgresDailySummaryProjector(session)
    touched = await daily_summary.apply(event)
    if touched is not None and redis_cache is not None:
        user_id, summary_date = touched
        await redis_cache.invalidate(user_id, summary_date)


class DiaryEventProjectorConsumer:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        redis_cache: RedisDailySummaryCache | None = None,
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
            await self._process(message)
            await message.ack()
        except Exception:
            logger.exception("diary_event_projection_failed", message_id=message.message_id)
            await self._retry_or_dead_letter(message)

    async def _process(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        body = json.loads(message.body.decode("utf-8"))
        event = _event_from_wire(body)

        async with self._session_factory() as session:
            processed_events = PostgresProcessedEventsRepository(session)
            if await processed_events.already_processed(event.event_id):
                return
            await apply_event_to_read_models(session, event, self._redis_cache)
            await processed_events.mark_processed(event.event_id)
            await session.commit()

    async def _retry_or_dead_letter(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        assert self._channel is not None
        headers = dict(message.headers or {})
        # aio_pika types a header value as a broad union (bytes/Decimal/
        # FieldArray/FieldTable/float/int/str/datetime/None) since AMQP
        # headers are dynamically typed on the wire -- this service only
        # ever writes an int here (below), so the narrow cast is safe.
        attempt = int(headers.get(RETRY_HEADER, 0)) + 1  # type: ignore[arg-type]

        if attempt > self._max_attempts:
            target_queue_name = DLQ_NAME
            logger.error(
                "diary_event_projection_dead_lettered",
                message_id=message.message_id,
                attempts=attempt,
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
