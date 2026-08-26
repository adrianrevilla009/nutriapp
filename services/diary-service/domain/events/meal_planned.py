"""MealPlanned (v1) -- see docs/events-catalog.md."""

from __future__ import annotations

import uuid
from datetime import datetime

from domain.events.base import DomainEvent, EventMetadata
from domain.value_objects.food_source import FoodSource
from domain.value_objects.meal_slot import MealSlot

EVENT_TYPE = "MealPlanned"
EVENT_VERSION = 1


def build_meal_planned_event(
    plan_entry_id: uuid.UUID,
    user_id: uuid.UUID,
    source: FoodSource,
    meal_slot: MealSlot,
    planned_for: datetime,
    correlation_id: str,
) -> DomainEvent:
    payload = {
        "plan_entry_id": str(plan_entry_id),
        "user_id": str(user_id),
        "source": source.to_dict(),
        "meal_slot": meal_slot.value,
        "planned_for": planned_for.isoformat(),
    }
    metadata = EventMetadata(correlation_id=correlation_id, user_id=str(user_id))
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(plan_entry_id),
        payload=payload,
        metadata=metadata,
    )
