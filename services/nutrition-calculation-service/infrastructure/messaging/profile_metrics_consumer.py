"""RabbitMqProfileMetricsConsumer -- this service's live inbound dependency
on profile-service's event stream (implementation plan Addendum 1).
Consumes profile-service's `profile.events` topic exchange, routing key
`profile.profile.*`, and triggers `RecomputeNutritionTargetHandler` on
`WeightRecorded`/`BodyMetricRecorded`/`GoalSet`/`GoalUpdated`.

Per Addendum 1: this consumer never reads or decrypts the ciphertext
fields carried by those events (`weight_kg`/`value`/`target_value`) -- it
uses the event purely as a trigger (`user_id` + which event type fired),
and the handler fetches plaintext metrics itself via `ProfileRevealPort`.

Idempotent by `(consumer_name, event_id)` via `ProcessedEventsPort` --
test-plan section 2's idempotency case asserts this via a fake
`ProfileRevealPort` call-count (replaying the same event must not call
`reveal()` twice).

Fallback (implementation plan section 7 / Addendum 1 security sub-addendum
requirement 7): if `RecomputeNutritionTargetHandler` raises
`RecomputeNutritionTargetDeferredError` (reveal circuit open/failed, or an
unresolved `Sex.OTHER` calculation-constant selection), this consumer logs
it and returns cleanly -- no crash, no retry storm, no
`NutritionTargetUpdated` published, left for the next triggering event.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any

import aio_pika
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.recompute_nutrition_target import (
    RecomputeNutritionTargetCommand,
    RecomputeNutritionTargetDeferredError,
    RecomputeNutritionTargetHandler,
)
from domain.ports.profile_reveal_port import ProfileRevealPort
from infrastructure.caching.redis_current_target_cache import RedisCurrentTargetCache
from infrastructure.persistence.postgres_nutrition_target_repository import (
    PostgresNutritionTargetRepository,
)
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from infrastructure.persistence.postgres_processed_events_repository import (
    PostgresProcessedEventsRepository,
)
from infrastructure.persistence.postgres_target_history_repository import (
    PostgresTargetHistoryRepository,
)
from infrastructure.persistence.postgres_user_metrics_snapshot_repository import (
    PostgresUserMetricsSnapshotRepository,
)

logger = structlog.get_logger()

EXCHANGE_NAME = "profile.events"
BINDING_ROUTING_KEY = "profile.profile.*"
QUEUE_NAME = "nutrition-calculation-service.profile_metrics"
DLQ_NAME = "nutrition-calculation-service.profile_metrics.dlq"
RETRY_HEADER = "x-nutrition-calc-retry-count"
MAX_DELIVERY_ATTEMPTS = 5
CONSUMER_NAME = "profile_metrics"

_RECOMPUTE_EVENT_TYPES = {"WeightRecorded", "BodyMetricRecorded", "GoalSet", "GoalUpdated"}


class ProfileMetricsConsumer:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        profile_reveal_port: ProfileRevealPort,
        redis_cache: RedisCurrentTargetCache | None = None,
        max_attempts: int = MAX_DELIVERY_ATTEMPTS,
    ) -> None:
        self._session_factory = session_factory
        self._profile_reveal_port = profile_reveal_port
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
            logger.exception("profile_metrics_processing_failed", message_id=message.message_id)
            await self._retry_or_dead_letter(message)

    async def process_body(self, body: dict[str, Any]) -> None:
        """Public so integration tests can exercise processing without a
        real broker connection."""
        event_type = body["event_type"]
        if event_type not in _RECOMPUTE_EVENT_TYPES:
            return

        event_id = uuid.UUID(body["event_id"])
        payload = body["payload"]
        user_id = uuid.UUID(payload["user_id"])
        correlation_id = body["metadata"]["correlation_id"]

        async with self._session_factory() as session:
            processed_events = PostgresProcessedEventsRepository(session)
            if await processed_events.already_processed(CONSUMER_NAME, event_id):
                return

            target_repository = PostgresNutritionTargetRepository(session)
            history_repository = PostgresTargetHistoryRepository(session)
            snapshot_repository = PostgresUserMetricsSnapshotRepository(session)
            outbox = PostgresOutboxRepository(session)
            handler = RecomputeNutritionTargetHandler(
                self._profile_reveal_port,
                target_repository,
                history_repository,
                snapshot_repository,
                outbox,
            )
            command = RecomputeNutritionTargetCommand(
                user_id=user_id, trigger_event_type=event_type, correlation_id=correlation_id
            )
            try:
                await handler.handle(command)
            except RecomputeNutritionTargetDeferredError as exc:
                logger.warning(
                    "nutrition_target_recompute_deferred",
                    user_id=str(user_id),
                    trigger_event_type=event_type,
                    reason=str(exc),
                )
                await processed_events.mark_processed(CONSUMER_NAME, event_id)
                await session.commit()
                return

            await processed_events.mark_processed(CONSUMER_NAME, event_id)
            await session.commit()

        if self._redis_cache is not None:
            await self._redis_cache.invalidate(user_id)

    async def _retry_or_dead_letter(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        assert self._channel is not None
        headers = dict(message.headers or {})
        attempt = int(headers.get(RETRY_HEADER, 0)) + 1  # type: ignore[arg-type]

        if attempt > self._max_attempts:
            target_queue_name = DLQ_NAME
            logger.error(
                "profile_metrics_dead_lettered", message_id=message.message_id, attempts=attempt
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
