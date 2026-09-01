"""ResilientTopicConsumer -- the aio_pika setup/consume/retry-then-dead-
letter plumbing shared internally by `BillingEventsConsumer` and
`RecipeEventsConsumer`. This service subscribes to two independent
upstream topic exchanges (billing-service's `billing.events`,
recipe-service's `recipe.events`); both consumers need the exact same
"redeliver up to N times, then dead-letter" failure handling
(messaging-conventions SKILL.md), so that plumbing lives here once and
each concrete consumer supplies only what's specific to its own upstream:
the exchange/queue/routing-key names and how to turn a decoded event
into a call on its own application-layer handlers.

This is an internal convenience within social-service's own codebase --
NOT a shared package imported by another service (CLAUDE.md section
2.5's one-independent-copy-per-service rule is about cross-service
sharing, not about a single service's own infrastructure layer being
allowed to factor out its own repetition)."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any

import aio_pika
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

DEFAULT_MAX_DELIVERY_ATTEMPTS = 5


class ResilientTopicConsumer:
    """Subclasses set the four `*_name`/`*_key` class attributes and
    implement `dispatch()`; everything else (queue setup, ack/retry/
    dead-letter bookkeeping) is inherited as-is."""

    exchange_name: str
    binding_routing_key: str
    queue_name: str
    dlq_name: str
    retry_header: str
    processing_failed_log_event: str
    dead_lettered_log_event: str

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        max_attempts: int = DEFAULT_MAX_DELIVERY_ATTEMPTS,
    ) -> None:
        self._session_factory = session_factory
        self._max_attempts = max_attempts
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._queue: aio_pika.abc.AbstractQueue | None = None

    async def dispatch(
        self, session: AsyncSession, event_type: str, event_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        """Applies one decoded event within the given session. Concrete
        consumers override this to route to their own command handlers."""
        raise NotImplementedError

    async def setup(
        self, connection: aio_pika.abc.AbstractRobustConnection
    ) -> aio_pika.abc.AbstractQueue:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=20)
        exchange = await channel.declare_exchange(
            self.exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
        )
        await channel.declare_queue(self.dlq_name, durable=True)
        queue = await channel.declare_queue(self.queue_name, durable=True)
        await queue.bind(exchange, routing_key=self.binding_routing_key)

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
            logger.exception(self.processing_failed_log_event, message_id=message.message_id)
            await self._retry_or_dead_letter(message)

    async def process_body(self, body: dict[str, Any]) -> None:
        """Public so integration tests can exercise processing without a
        real broker connection."""
        event_type = body["event_type"]
        event_id = uuid.UUID(body["event_id"])
        payload = body["payload"]

        async with self._session_factory() as session:
            await self.dispatch(session, event_type, event_id, payload)
            await session.commit()

    async def _retry_or_dead_letter(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        assert self._channel is not None
        headers = dict(message.headers or {})
        attempt = int(headers.get(self.retry_header, 0)) + 1  # type: ignore[arg-type]

        if attempt > self._max_attempts:
            target_queue_name = self.dlq_name
            logger.error(
                self.dead_lettered_log_event, message_id=message.message_id, attempts=attempt
            )
        else:
            target_queue_name = self.queue_name
            headers[self.retry_header] = attempt

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
