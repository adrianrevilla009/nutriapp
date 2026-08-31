"""HandleRecipePublishedHandler -- consumes recipe-service's
`RecipePublished` (v1), the feed-projection side of fan-out-on-read
(implementation plan section 1.3). Upserts a `feed_entries` row keyed by
`recipe_id`. Idempotent by `event_id`, via `ProcessedRecipeEventsRepositoryPort`
-- a SEPARATE idempotency ledger from `ProcessedEntitlementEventsRepositoryPort`
(implementation plan section 3, two independent consumers).

**Known, flagged gap**: `RecipePublished` (v1)'s actual payload
(`packages/shared-contracts/schemas/recipe_published.v1.json`) is
`{recipe_id, user_id, published_at}` -- no `title`. The consumer
(`infrastructure/messaging/recipe_events_consumer.py`) reads `title` via
`payload.get("title")`, defensively forward-compatible with a future
`RecipePublished` v2 that adds it, but today this is always `None` -- see
`domain/value_objects/feed_entry.py`'s docstring for the full reasoning,
and the final implementation report for the recommended follow-up."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.ports.feed_repository_port import FeedRepositoryPort
from domain.ports.processed_recipe_events_repository_port import (
    ProcessedRecipeEventsRepositoryPort,
)
from domain.value_objects.feed_entry import FeedEntry


@dataclass(frozen=True, slots=True)
class HandleRecipePublishedCommand:
    event_id: uuid.UUID
    recipe_id: uuid.UUID
    author_id: uuid.UUID
    title: str | None
    published_at: datetime


class HandleRecipePublishedHandler:
    def __init__(
        self,
        processed_events: ProcessedRecipeEventsRepositoryPort,
        feed: FeedRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._feed = feed

    async def handle(self, command: HandleRecipePublishedCommand) -> None:
        if await self._processed_events.is_processed(command.event_id):
            return
        entry = FeedEntry(
            recipe_id=command.recipe_id,
            author_id=command.author_id,
            title=command.title,
            published_at=command.published_at,
        )
        await self._feed.upsert(entry)
        await self._processed_events.mark_processed(command.event_id)
