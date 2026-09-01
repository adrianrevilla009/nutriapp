"""HandleRecipeUnpublishedHandler -- consumes recipe-service's
`RecipeUnpublished` (v1). Removes the corresponding `feed_entries` row
SYNCHRONOUSLY with consumption -- never a scheduled recompute
(social-agent.md's "must take effect immediately" rule, implementation
plan section 1.4's privacy-enforcement reading). Idempotent: a recipe with
no existing `feed_entries` row (never published in this consumer's
lifetime, or already removed) is a no-op, no error. Same independent
idempotency ledger as `HandleRecipePublishedHandler`."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.ports.feed_repository_port import FeedRepositoryPort
from domain.ports.processed_recipe_events_repository_port import (
    ProcessedRecipeEventsRepositoryPort,
)


@dataclass(frozen=True, slots=True)
class HandleRecipeUnpublishedCommand:
    event_id: uuid.UUID
    recipe_id: uuid.UUID


class HandleRecipeUnpublishedHandler:
    def __init__(
        self,
        processed_events: ProcessedRecipeEventsRepositoryPort,
        feed: FeedRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._feed = feed

    async def handle(self, command: HandleRecipeUnpublishedCommand) -> None:
        if await self._processed_events.is_processed(command.event_id):
            return
        await self._feed.delete_by_recipe_id(command.recipe_id)
        await self._processed_events.mark_processed(command.event_id)
