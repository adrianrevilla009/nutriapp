"""RecipeCreated (v1) -- see docs/events-catalog.md. Published via Outbox
in the same DB transaction as the recipe row (ADR-0002 event-driven CRUD).
`aggregate_id` is the `recipe_id`.
"""

from __future__ import annotations

import uuid

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "RecipeCreated"
EVENT_VERSION = 1


def build_recipe_created_event(
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
