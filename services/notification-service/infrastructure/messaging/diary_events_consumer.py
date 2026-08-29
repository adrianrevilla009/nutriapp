"""DiaryEventsConsumer -- subscribes to diary-service's own `diary.events`
topic exchange (routing key `diary.#`, catching all 10 event types that
service publishes) and dispatches the 7 events this plan actually
consumes (FastingWindowStarted/Ended, MealPlanned/Updated/Removed,
WaterIntakeLogged/Removed) to UpdateReminderScheduleHandler -- everything
else (FoodEntry*) is acknowledged and ignored.

Idempotent by (event_id, channel="push") at the consumer level (dedup
before dispatch) -- belt-and-suspenders with the projector's own natural
upsert idempotency (keyed by (source_aggregate_id, category), see
postgres_reminder_schedule_repository.py), satisfying test-plan section
1's "same end state whether applied once or twice" requirement two ways.

Failure handling: same retry/DLQ shape as identity_events_consumer.py and
diary-service's own diary_event_projector_consumer.py.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable

import aio_pika
import structlog
from shared_contracts.events.diary import (
    FastingWindowEndedPayloadV1,
    FastingWindowStartedPayloadV1,
    MealPlannedPayloadV1,
    MealPlanRemovedPayloadV1,
    MealPlanUpdatedPayloadV1,
    WaterIntakeLoggedPayloadV1,
    WaterIntakeRemovedPayloadV1,
)
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.update_reminder_schedule import (
    FastingWindowEndedCommand,
    FastingWindowStartedCommand,
    MealPlannedCommand,
    MealPlanRemovedCommand,
    MealPlanUpdatedCommand,
    UpdateReminderScheduleHandler,
    WaterIntakeLoggedCommand,
    WaterIntakeRemovedCommand,
)
from infrastructure.persistence.postgres_processed_notifications_repository import (
    PostgresProcessedNotificationsRepository,
)
from infrastructure.persistence.postgres_reminder_schedule_repository import (
    PostgresReminderScheduleRepository,
)

logger = structlog.get_logger()

EXCHANGE_NAME = "diary.events"
BINDING_ROUTING_KEY = "diary.#"
QUEUE_NAME = "notification-service.diary_events"
DLQ_NAME = "notification-service.diary_events.dlq"
RETRY_HEADER = "x-notification-retry-count"
MAX_DELIVERY_ATTEMPTS = 5
CHANNEL = "push"


async def dispatch_diary_event(
    session: AsyncSession, event_type: str, event_id: uuid.UUID, payload: dict[str, object]
) -> None:
    reminder_schedule = PostgresReminderScheduleRepository(session)
    handler = UpdateReminderScheduleHandler(reminder_schedule)

    if event_type == "FastingWindowStarted":
        started = FastingWindowStartedPayloadV1.model_validate(payload)
        await handler.handle_fasting_window_started(
            FastingWindowStartedCommand(
                event_id=event_id,
                window_id=started.window_id,
                user_id=started.user_id,
                started_at=started.started_at,
            )
        )
    elif event_type == "FastingWindowEnded":
        ended = FastingWindowEndedPayloadV1.model_validate(payload)
        await handler.handle_fasting_window_ended(
            FastingWindowEndedCommand(
                event_id=event_id,
                window_id=ended.window_id,
                user_id=ended.user_id,
                ended_at=ended.ended_at,
            )
        )
    elif event_type == "MealPlanned":
        planned = MealPlannedPayloadV1.model_validate(payload)
        await handler.handle_meal_planned(
            MealPlannedCommand(
                event_id=event_id,
                plan_entry_id=planned.plan_entry_id,
                user_id=planned.user_id,
                planned_for=planned.planned_for,
            )
        )
    elif event_type == "MealPlanUpdated":
        updated = MealPlanUpdatedPayloadV1.model_validate(payload)
        await handler.handle_meal_plan_updated(
            MealPlanUpdatedCommand(
                event_id=event_id,
                plan_entry_id=updated.plan_entry_id,
                user_id=updated.user_id,
                planned_for=updated.planned_for,
            )
        )
    elif event_type == "MealPlanRemoved":
        removed = MealPlanRemovedPayloadV1.model_validate(payload)
        await handler.handle_meal_plan_removed(
            MealPlanRemovedCommand(
                event_id=event_id,
                plan_entry_id=removed.plan_entry_id,
                user_id=removed.user_id,
                removed_at=removed.removed_at,
            )
        )
    elif event_type == "WaterIntakeLogged":
        logged = WaterIntakeLoggedPayloadV1.model_validate(payload)
        await handler.handle_water_intake_logged(
            WaterIntakeLoggedCommand(
                event_id=event_id,
                intake_id=logged.intake_id,
                user_id=logged.user_id,
                occurred_at=logged.occurred_at,
            )
        )
    elif event_type == "WaterIntakeRemoved":
        water_removed = WaterIntakeRemovedPayloadV1.model_validate(payload)
        await handler.handle_water_intake_removed(
            WaterIntakeRemovedCommand(
                event_id=event_id,
                intake_id=water_removed.intake_id,
                user_id=water_removed.user_id,
                removed_at=water_removed.removed_at,
            )
        )
    # else: a diary event this service doesn't project (FoodEntry*) -- ack, ignore.


class DiaryEventsConsumer:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        max_attempts: int = MAX_DELIVERY_ATTEMPTS,
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
            await self._process(message)
            await message.ack()
        except Exception:
            logger.exception(
                "diary_event_reminder_projection_failed", message_id=message.message_id
            )
            await self._retry_or_dead_letter(message)

    async def _process(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        body = json.loads(message.body.decode("utf-8"))
        event_id = uuid.UUID(body["event_id"])
        event_type = body["event_type"]
        payload = body["payload"]

        async with self._session_factory() as session:
            processed = PostgresProcessedNotificationsRepository(session)
            if await processed.already_processed(event_id, CHANNEL):
                return
            await dispatch_diary_event(session, event_type, event_id, payload)
            await processed.mark_processed(event_id, CHANNEL)
            await session.commit()

    async def _retry_or_dead_letter(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        assert self._channel is not None
        headers = dict(message.headers or {})
        attempt = int(headers.get(RETRY_HEADER, 0)) + 1  # type: ignore[arg-type]

        if attempt > self._max_attempts:
            target_queue_name = DLQ_NAME
            logger.error(
                "diary_event_reminder_projection_dead_lettered",
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
