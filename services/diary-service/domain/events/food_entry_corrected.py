"""FoodEntryCorrected (v1) -- see docs/events-catalog.md.

Same shape as FoodEntryLogged (full replacement of the correctable fields
-- source/meal_slot/occurred_at), plus corrected_at. Never mutates the
original FoodEntryLogged row; a projector interprets the pair."""

from __future__ import annotations

import uuid
from datetime import datetime

from domain.events.base import DomainEvent, EventMetadata
from domain.value_objects.food_source import FoodSource
from domain.value_objects.meal_slot import MealSlot

EVENT_TYPE = "FoodEntryCorrected"
EVENT_VERSION = 1


def build_food_entry_corrected_event(
    entry_id: uuid.UUID,
    user_id: uuid.UUID,
    source: FoodSource,
    meal_slot: MealSlot,
    occurred_at: datetime,
    corrected_at: datetime,
    correlation_id: str,
) -> DomainEvent:
    payload = {
        "entry_id": str(entry_id),
        "user_id": str(user_id),
        "source": source.to_dict(),
        "meal_slot": meal_slot.value,
        "occurred_at": occurred_at.isoformat(),
        "corrected_at": corrected_at.isoformat(),
    }
    metadata = EventMetadata(correlation_id=correlation_id, user_id=str(user_id))
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(entry_id),
        payload=payload,
        metadata=metadata,
    )
