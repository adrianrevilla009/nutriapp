"""FoodEntry aggregate root -- full event sourcing (ADR-0002). One
instance per logged item (aggregate_id = entry_id), implementation plan
section 2. Current state is never stored directly; it is always derived
by folding over the aggregate's event stream (`rebuild`). A correction or
deletion is always a new event, never a mutation of a prior one.

Zero framework imports (ADR-0001).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.events.base import DomainEvent
from domain.events.food_entry_corrected import build_food_entry_corrected_event
from domain.events.food_entry_deleted import build_food_entry_deleted_event
from domain.events.food_entry_logged import build_food_entry_logged_event
from domain.value_objects.food_source import FoodSource
from domain.value_objects.meal_slot import MealSlot


class FoodEntryNotFoundError(Exception):
    """Raised when rebuild() is given an empty event stream."""


class EntryAlreadyDeletedError(Exception):
    """Raised when correct() or delete() is called on an already-deleted entry."""


@dataclass(slots=True)
class FoodEntry:
    entry_id: uuid.UUID
    user_id: uuid.UUID | None = None
    source: FoodSource | None = None
    meal_slot: MealSlot | None = None
    occurred_at: datetime | None = None
    deleted: bool = False

    @classmethod
    def rebuild(cls, events: list[DomainEvent]) -> FoodEntry:
        if not events:
            raise FoodEntryNotFoundError("Cannot rebuild a food entry from an empty event stream.")
        state = cls(entry_id=uuid.UUID(events[0].payload["entry_id"]))
        for event in events:
            state.apply(event)
        return state

    def apply(self, event: DomainEvent) -> None:
        handler = getattr(self, f"_apply_{event.handler_method_suffix}", None)
        if handler is not None:
            handler(event)

    def _apply_food_entry_logged(self, event: DomainEvent) -> None:
        self.user_id = uuid.UUID(event.payload["user_id"])
        self.source = FoodSource.from_dict(event.payload["source"])
        self.meal_slot = MealSlot.from_value(event.payload["meal_slot"])
        self.occurred_at = datetime.fromisoformat(event.payload["occurred_at"])

    def _apply_food_entry_corrected(self, event: DomainEvent) -> None:
        self.source = FoodSource.from_dict(event.payload["source"])
        self.meal_slot = MealSlot.from_value(event.payload["meal_slot"])
        self.occurred_at = datetime.fromisoformat(event.payload["occurred_at"])

    def _apply_food_entry_deleted(self, event: DomainEvent) -> None:
        self.deleted = True

    @classmethod
    def log(
        cls,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
        source: FoodSource,
        meal_slot: MealSlot,
        occurred_at: datetime,
        correlation_id: str,
    ) -> tuple[FoodEntry, DomainEvent]:
        entry = cls(entry_id=entry_id)
        event = build_food_entry_logged_event(
            entry_id=entry_id,
            user_id=user_id,
            source=source,
            meal_slot=meal_slot,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
        )
        entry.apply(event)
        return entry, event

    def correct(
        self,
        source: FoodSource,
        meal_slot: MealSlot,
        occurred_at: datetime,
        corrected_at: datetime,
        correlation_id: str,
    ) -> DomainEvent:
        if self.deleted:
            raise EntryAlreadyDeletedError("Cannot correct a deleted food entry.")
        assert self.user_id is not None
        event = build_food_entry_corrected_event(
            entry_id=self.entry_id,
            user_id=self.user_id,
            source=source,
            meal_slot=meal_slot,
            occurred_at=occurred_at,
            corrected_at=corrected_at,
            correlation_id=correlation_id,
        )
        self.apply(event)
        return event

    def delete(self, deleted_at: datetime, correlation_id: str) -> DomainEvent:
        if self.deleted:
            raise EntryAlreadyDeletedError("Food entry is already deleted.")
        assert self.user_id is not None
        event = build_food_entry_deleted_event(
            entry_id=self.entry_id,
            user_id=self.user_id,
            deleted_at=deleted_at,
            correlation_id=correlation_id,
        )
        self.apply(event)
        return event
