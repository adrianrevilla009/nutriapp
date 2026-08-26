"""MealPlanUpdated (v1) -- see docs/events-catalog.md.

Same shape as MealPlanned, plus updated_at. Original MealPlanned event
is never mutated -- a projector interprets the pair."""

from __future__ import annotations

import uuid
from datetime import datetime

from domain.events.base import DomainEvent, EventMetadata
from domain.value_objects.food_source import FoodSource
from domain.value_objects.meal_slot import MealSlot

EVENT_TYPE = "MealPlanUpdated"
EVENT_VERSION = 1


def build_meal_plan_updated_event(
    plan_entry_id: uuid.UUID,
    user_id: uuid.UUID,
    source: FoodSource,
    meal_slot: MealSlot,
    planned_for: datetime,
    updated_at: datetime,
    correlation_id: str,
) -> DomainEvent:
    payload = {
        "plan_entry_id": str(plan_entry_id),
        "user_id": str(user_id),
        "source": source.to_dict(),
        "meal_slot": meal_slot.value,
        "planned_for": planned_for.isoformat(),
        "updated_at": updated_at.isoformat(),
    }
    metadata = EventMetadata(correlation_id=correlation_id, user_id=str(user_id))
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(plan_entry_id),
        payload=payload,
        metadata=metadata,
    )
