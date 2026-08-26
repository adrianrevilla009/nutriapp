"""FoodEntryDeleted (v1) -- see docs/events-catalog.md."""

from __future__ import annotations

import uuid
from datetime import datetime

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "FoodEntryDeleted"
EVENT_VERSION = 1


def build_food_entry_deleted_event(
    entry_id: uuid.UUID, user_id: uuid.UUID, deleted_at: datetime, correlation_id: str
) -> DomainEvent:
    payload = {
        "entry_id": str(entry_id),
        "user_id": str(user_id),
        "deleted_at": deleted_at.isoformat(),
    }
    metadata = EventMetadata(correlation_id=correlation_id, user_id=str(user_id))
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(entry_id),
        payload=payload,
        metadata=metadata,
    )
