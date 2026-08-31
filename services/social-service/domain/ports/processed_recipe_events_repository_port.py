"""ProcessedRecipeEventsRepositoryPort -- idempotency dedup for
`recipe_events_consumer.py`'s `RecipePublished`/`RecipeUnpublished`
handling, keyed by `event_id` alone. Deliberately a SEPARATE table/port
from `ProcessedEntitlementEventsRepositoryPort` -- two independent
consumers, two independent idempotency ledgers (implementation plan
section 3)."""

from __future__ import annotations

import uuid
from typing import Protocol


class ProcessedRecipeEventsRepositoryPort(Protocol):
    async def is_processed(self, event_id: uuid.UUID) -> bool: ...

    async def mark_processed(self, event_id: uuid.UUID) -> None: ...
