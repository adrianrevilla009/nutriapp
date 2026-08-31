"""RecipePublished (v1) -- see docs/events-catalog.md. Published only
after the entitlement check passes AND every ingredient re-resolves
against `catalog-service` at publish time (recipe-agent.md: never publish
incomplete data)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "RecipePublished"
EVENT_VERSION = 1


def build_recipe_published_event(
    *, recipe_id: uuid.UUID, user_id: uuid.UUID, correlation_id: str
) -> DomainEvent:
    payload = {
        "recipe_id": str(recipe_id),
        "user_id": str(user_id),
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(recipe_id),
        payload=payload,
        metadata=EventMetadata(correlation_id=correlation_id, user_id=str(user_id)),
    )
