"""UserRegisteredConsumer -- profile-service's first live inbound
dependency on identity-service's event stream (implementation plan
section 6). Consumes identity-service's `identity.events` topic exchange,
routing key `identity.user.registered`, and creates an empty profile
aggregate for that user_id (reactive, no synchronous call back to
identity-service).

Idempotent by event_id (messaging-conventions SKILL.md) -- enforced by
CreateProfileOnUserRegisteredHandler via ProcessedEventsPort, not by this
consumer itself, so redelivery after a crash mid-processing is always
safe.

Failure handling (messaging-conventions SKILL.md, test-plan section 2): a
message that raises is retried up to MAX_DELIVERY_ATTEMPTS times (a
manually incremented `x-profile-retry-count` header, republished to the
same queue and the original ack'd -- classic queues do not expose a
native per-message delivery counter), then republished to the dead-letter
queue instead of being retried forever or dropped silently.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable

import aio_pika
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.create_profile_on_user_registered import (
    CreateProfileOnUserRegisteredCommand,
    CreateProfileOnUserRegisteredHandler,
)
from infrastructure.persistence.postgres_event_store import PostgresEventStore
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from infrastructure.persistence.postgres_processed_events_repository import (
    PostgresProcessedEventsRepository,
)

logger = structlog.get_logger()

IDENTITY_EXCHANGE_NAME = "identity.events"
IDENTITY_USER_REGISTERED_ROUTING_KEY = "identity.user.registered"
QUEUE_NAME = "profile-service.user_registered"
DLQ_NAME = "profile-service.user_registered.dlq"
RETRY_HEADER = "x-profile-retry-count"
MAX_DELIVERY_ATTEMPTS = 5


class UserRegisteredConsumer:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        max_attempts: int = MAX_DELIVERY_ATTEMPTS,
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
        await channel.set_qos(prefetch_count=10)
        exchange = await channel.declare_exchange(
            IDENTITY_EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        dlq = await channel.declare_queue(DLQ_NAME, durable=True)
        queue = await channel.declare_queue(QUEUE_NAME, durable=True)
        await queue.bind(exchange, routing_key=IDENTITY_USER_REGISTERED_ROUTING_KEY)

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
            logger.exception("user_registered_processing_failed", message_id=message.message_id)
            await self._retry_or_dead_letter(message)

    async def _process(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        body = json.loads(message.body.decode("utf-8"))
        user_id = uuid.UUID(body["payload"]["user_id"])
        source_event_id = uuid.UUID(body["event_id"])
        correlation_id = body["metadata"]["correlation_id"]

        async with self._session_factory() as session:
            event_store = PostgresEventStore(session)
            outbox = PostgresOutboxRepository(session)
            processed_events = PostgresProcessedEventsRepository(session)
            handler = CreateProfileOnUserRegisteredHandler(event_store, outbox, processed_events)
            await handler.handle(
                CreateProfileOnUserRegisteredCommand(
                    user_id=user_id, source_event_id=source_event_id, correlation_id=correlation_id
                )
            )
            await session.commit()

    async def _retry_or_dead_letter(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        assert self._channel is not None
        headers = dict(message.headers or {})
        # headers are dynamically typed on the wire -- this service only
        # ever writes an int here (below), so the narrow cast is safe.
        attempt = int(headers.get(RETRY_HEADER, 0)) + 1  # type: ignore[arg-type]

        if attempt > self._max_attempts:
            target_queue_name = DLQ_NAME
            logger.error(
                "user_registered_dead_lettered", message_id=message.message_id, attempts=attempt
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
