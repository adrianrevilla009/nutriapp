"""RecipeUpdated (v1) -- see docs/events-catalog.md. Published exactly
once per successful `PATCH /api/v1/recipes/{recipe_id}` (test-plan
section 1's `UpdateRecipeHandler` case)."""

from __future__ import annotations

import uuid

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "RecipeUpdated"
EVENT_VERSION = 1


def build_recipe_updated_event(
    *, recipe_id: uuid.UUID, user_id: uuid.UUID, correlation_id: str
) -> DomainEvent:
    payload = {"recipe_id": str(recipe_id), "user_id": str(user_id)}
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(recipe_id),
        payload=payload,
        metadata=EventMetadata(correlation_id=correlation_id, user_id=str(user_id)),
    )
