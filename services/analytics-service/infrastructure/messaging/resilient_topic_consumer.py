"""ResilientTopicConsumer -- the aio_pika setup/consume/retry-then-dead-
letter plumbing shared by this service's four topic consumers
(diary/profile/nutrition_calculation/billing). Same internal-convenience
pattern as social-service's own module of the same name (CLAUDE.md
section 2.5: not a shared package, each service's own copy)."""

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
        self,
        session: AsyncSession,
        event_type: str,
        event_id: uuid.UUID,
        payload: dict[str, Any],
        metadata: dict[str, Any],
    ) -> None:
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
        event_type = body["event_type"]
        event_id = uuid.UUID(body["event_id"])
        payload = body["payload"]
        metadata = body.get("metadata", {})

        async with self._session_factory() as session:
            await self.dispatch(session, event_type, event_id, payload, metadata)
            await session.commit()

    async def _retry_or_dead_letter(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        assert self._channel is not None
        headers = dict(message.headers or {})
        # aio_pika types message headers as a loosely-typed mapping whose
        # values are its own `FieldValue` union, which mypy can't narrow
        # to `int` -- but this header's value is only ever an `int` this
        # same method wrote on a prior retry (or absent, defaulting to 0
        # via .get()). Genuine false positive, not a suppressed real
        # finding.
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
