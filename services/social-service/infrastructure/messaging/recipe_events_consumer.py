"""RecipeEventsConsumer -- subscribes to recipe-service's `recipe.events`
topic exchange (routing key `recipe.recipe.*`) and dispatches
`RecipePublished`/`RecipeUnpublished` to their command handlers, projecting
this service's local `feed_entries` read table (fan-out-on-read,
implementation plan section 1.3) -- the FIRST real consumer of either
event in this codebase.

Idempotent by `event_id` via `ProcessedRecipeEventsRepositoryPort` -- a
SEPARATE idempotency ledger from `ProcessedEntitlementEventsRepositoryPort`
(implementation plan section 3, two independent consumers). Any other
recipe event type (`RecipeCreated`/`RecipeUpdated`) is acknowledged and
ignored -- this service only cares about published/unpublished state,
never draft authoring.

Failure handling identical to `billing_events_consumer.py` -- retried up
to `MAX_DELIVERY_ATTEMPTS` then dead-lettered, never dropped silently."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

import aio_pika
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.handle_recipe_published import (
    HandleRecipePublishedCommand,
    HandleRecipePublishedHandler,
)
from application.commands.handle_recipe_unpublished import (
    HandleRecipeUnpublishedCommand,
    HandleRecipeUnpublishedHandler,
)
from infrastructure.persistence.postgres_feed_repository import PostgresFeedRepository
from infrastructure.persistence.postgres_processed_recipe_events_repository import (
    PostgresProcessedRecipeEventsRepository,
)

logger = structlog.get_logger()

EXCHANGE_NAME = "recipe.events"
BINDING_ROUTING_KEY = "recipe.recipe.*"
QUEUE_NAME = "social-service.recipe_events"
DLQ_NAME = "social-service.recipe_events.dlq"
RETRY_HEADER = "x-social-service-recipe-retry-count"
MAX_DELIVERY_ATTEMPTS = 5

_HANDLED_EVENT_TYPES = {"RecipePublished", "RecipeUnpublished"}


async def dispatch_recipe_event(
    session: AsyncSession, event_type: str, event_id: uuid.UUID, payload: dict[str, Any]
) -> None:
    """Shared dispatch helper -- mirrors billing_events_consumer.py's
    `dispatch_billing_event` precedent."""
    if event_type not in _HANDLED_EVENT_TYPES:
        return

    processed_events = PostgresProcessedRecipeEventsRepository(session)
    feed = PostgresFeedRepository(session)

    if event_type == "RecipePublished":
        published_handler = HandleRecipePublishedHandler(processed_events, feed)
        await published_handler.handle(
            HandleRecipePublishedCommand(
                event_id=event_id,
                recipe_id=uuid.UUID(str(payload["recipe_id"])),
                author_id=uuid.UUID(str(payload["user_id"])),
                # Known gap -- RecipePublished (v1) does not carry a title
                # today; see domain/value_objects/feed_entry.py's docstring.
                title=payload.get("title"),
                published_at=datetime.fromisoformat(payload["published_at"]),
            )
        )
    elif event_type == "RecipeUnpublished":
        unpublished_handler = HandleRecipeUnpublishedHandler(processed_events, feed)
        await unpublished_handler.handle(
            HandleRecipeUnpublishedCommand(
                event_id=event_id,
                recipe_id=uuid.UUID(str(payload["recipe_id"])),
            )
        )


class RecipeEventsConsumer:
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
            logger.exception("recipe_event_processing_failed", message_id=message.message_id)
            await self._retry_or_dead_letter(message)

    async def process_body(self, body: dict[str, Any]) -> None:
        """Public so integration tests can exercise processing without a
        real broker connection."""
        event_type = body["event_type"]
        event_id = uuid.UUID(body["event_id"])
        payload = body["payload"]

        async with self._session_factory() as session:
            await dispatch_recipe_event(session, event_type, event_id, payload)
            await session.commit()

    async def _retry_or_dead_letter(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        assert self._channel is not None
        headers = dict(message.headers or {})
        attempt = int(headers.get(RETRY_HEADER, 0)) + 1  # type: ignore[arg-type]

        if attempt > self._max_attempts:
            target_queue_name = DLQ_NAME
            logger.error(
                "recipe_event_dead_lettered", message_id=message.message_id, attempts=attempt
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
