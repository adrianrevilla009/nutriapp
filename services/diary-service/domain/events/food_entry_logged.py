"""FoodEntryLogged (v1) -- see docs/events-catalog.md.

`planned_from_entry_id` is an additive, nullable forward-compatibility
seam (implementation plan section 9.3) for a future "log from plan"
workflow -- not populated or read by anything in this implementation.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from domain.events.base import DomainEvent, EventMetadata
from domain.value_objects.food_source import FoodSource
from domain.value_objects.meal_slot import MealSlot

EVENT_TYPE = "FoodEntryLogged"
EVENT_VERSION = 1


def build_food_entry_logged_event(
    entry_id: uuid.UUID,
    user_id: uuid.UUID,
    source: FoodSource,
    meal_slot: MealSlot,
    occurred_at: datetime,
    correlation_id: str,
    planned_from_entry_id: uuid.UUID | None = None,
) -> DomainEvent:
    payload = {
        "entry_id": str(entry_id),
        "user_id": str(user_id),
        "source": source.to_dict(),
        "meal_slot": meal_slot.value,
        "occurred_at": occurred_at.isoformat(),
        "planned_from_entry_id": str(planned_from_entry_id) if planned_from_entry_id else None,
    }
    metadata = EventMetadata(correlation_id=correlation_id, user_id=str(user_id))
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(entry_id),
        payload=payload,
        metadata=metadata,
    )
