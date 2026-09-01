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

Queue setup and retry-then-dead-letter mechanics are shared with
`billing_events_consumer.py` via `resilient_topic_consumer.py`; unlike
that consumer's if/elif dispatch, this one routes through a small
per-event-type builder table (`_EVENT_BUILDERS`) since RecipePublished
and RecipeUnpublished construct their commands from disjoint payload
shapes."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.handle_recipe_published import (
    HandleRecipePublishedCommand,
    HandleRecipePublishedHandler,
)
from application.commands.handle_recipe_unpublished import (
    HandleRecipeUnpublishedCommand,
    HandleRecipeUnpublishedHandler,
)
from infrastructure.messaging.resilient_topic_consumer import ResilientTopicConsumer
from infrastructure.persistence.postgres_feed_repository import PostgresFeedRepository
from infrastructure.persistence.postgres_processed_recipe_events_repository import (
    PostgresProcessedRecipeEventsRepository,
)

EXCHANGE_NAME = "recipe.events"
BINDING_ROUTING_KEY = "recipe.recipe.*"
QUEUE_NAME = "social-service.recipe_events"
DLQ_NAME = "social-service.recipe_events.dlq"
RETRY_HEADER = "x-social-service-recipe-retry-count"


async def _apply_recipe_published(
    processed_events: PostgresProcessedRecipeEventsRepository,
    feed: PostgresFeedRepository,
    event_id: uuid.UUID,
    payload: dict[str, Any],
) -> None:
    await HandleRecipePublishedHandler(processed_events, feed).handle(
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


async def _apply_recipe_unpublished(
    processed_events: PostgresProcessedRecipeEventsRepository,
    feed: PostgresFeedRepository,
    event_id: uuid.UUID,
    payload: dict[str, Any],
) -> None:
    await HandleRecipeUnpublishedHandler(processed_events, feed).handle(
        HandleRecipeUnpublishedCommand(
            event_id=event_id,
            recipe_id=uuid.UUID(str(payload["recipe_id"])),
        )
    )


_EventApplier = Callable[
    [PostgresProcessedRecipeEventsRepository, PostgresFeedRepository, uuid.UUID, dict[str, Any]],
    Awaitable[None],
]

_EVENT_BUILDERS: dict[str, _EventApplier] = {
    "RecipePublished": _apply_recipe_published,
    "RecipeUnpublished": _apply_recipe_unpublished,
}


async def dispatch_recipe_event(
    session: AsyncSession, event_type: str, event_id: uuid.UUID, payload: dict[str, Any]
) -> None:
    """Standalone on purpose -- see `billing_events_consumer.dispatch_billing_event`
    for why this stays reusable outside of a live consumer instance."""
    apply_event = _EVENT_BUILDERS.get(event_type)
    if apply_event is None:
        return

    processed_events = PostgresProcessedRecipeEventsRepository(session)
    feed = PostgresFeedRepository(session)
    await apply_event(processed_events, feed, event_id, payload)


class RecipeEventsConsumer(ResilientTopicConsumer):
    exchange_name = EXCHANGE_NAME
    binding_routing_key = BINDING_ROUTING_KEY
    queue_name = QUEUE_NAME
    dlq_name = DLQ_NAME
    retry_header = RETRY_HEADER
    processing_failed_log_event = "recipe_event_processing_failed"
    dead_lettered_log_event = "recipe_event_dead_lettered"

    async def dispatch(
        self, session: AsyncSession, event_type: str, event_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        await dispatch_recipe_event(session, event_type, event_id, payload)
