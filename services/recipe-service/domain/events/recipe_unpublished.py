"""RecipeUnpublished (v1) -- NEW event, added to docs/events-catalog.md by
this plan (implementation-plan.md section 5). Emitted when a user
unpublishes or deletes a previously-published recipe -- removed from
cross-user search, author's own record/event history retained (never a
hard row delete -- recipe-agent.md). Never published for a recipe that
was never published in the first place (nothing to announce) or for an
already-unpublished recipe (idempotent no-op, test-plan section 1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "RecipeUnpublished"
EVENT_VERSION = 1


def build_recipe_unpublished_event(
    *, recipe_id: uuid.UUID, user_id: uuid.UUID, correlation_id: str
) -> DomainEvent:
    payload = {
        "recipe_id": str(recipe_id),
        "user_id": str(user_id),
        "unpublished_at": datetime.now(timezone.utc).isoformat(),
    }
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(recipe_id),
        payload=payload,
        metadata=EventMetadata(correlation_id=correlation_id, user_id=str(user_id)),
    )
