"""MealPlanEntry aggregate root -- full event sourcing (ADR-0002). One
instance per planned item (aggregate_id = plan_entry_id), implementation
plan section 2. Distinct from the as-eaten FoodEntry aggregate. An update
or removal is always a new event, never a mutation of a prior one.

Zero framework imports (ADR-0001).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.events.base import DomainEvent
from domain.events.meal_plan_removed import build_meal_plan_removed_event
from domain.events.meal_plan_updated import build_meal_plan_updated_event
from domain.events.meal_planned import build_meal_planned_event
from domain.value_objects.food_source import FoodSource
from domain.value_objects.meal_slot import MealSlot


class MealPlanEntryNotFoundError(Exception):
    """Raised when rebuild() is given an empty event stream."""


class PlanEntryAlreadyRemovedError(Exception):
    """Raised when update() or remove() is called on an already-removed plan entry."""


@dataclass(slots=True)
class MealPlanEntry:
    plan_entry_id: uuid.UUID
    user_id: uuid.UUID | None = None
    source: FoodSource | None = None
    meal_slot: MealSlot | None = None
    planned_for: datetime | None = None
    removed: bool = False

    @classmethod
    def rebuild(cls, events: list[DomainEvent]) -> MealPlanEntry:
        if not events:
            raise MealPlanEntryNotFoundError(
                "Cannot rebuild a meal plan entry from an empty event stream."
            )
        state = cls(plan_entry_id=uuid.UUID(events[0].payload["plan_entry_id"]))
        for event in events:
            state.apply(event)
        return state

    def apply(self, event: DomainEvent) -> None:
        handler = getattr(self, f"_apply_{event.event_type}", None)
        if handler is not None:
            handler(event)

    def _apply_MealPlanned(self, event: DomainEvent) -> None:
        self.user_id = uuid.UUID(event.payload["user_id"])
        self.source = FoodSource.from_dict(event.payload["source"])
        self.meal_slot = MealSlot.from_value(event.payload["meal_slot"])
        self.planned_for = datetime.fromisoformat(event.payload["planned_for"])

    def _apply_MealPlanUpdated(self, event: DomainEvent) -> None:
        self.source = FoodSource.from_dict(event.payload["source"])
        self.meal_slot = MealSlot.from_value(event.payload["meal_slot"])
        self.planned_for = datetime.fromisoformat(event.payload["planned_for"])

    def _apply_MealPlanRemoved(self, event: DomainEvent) -> None:
        self.removed = True

    @classmethod
    def plan(
        cls,
        plan_entry_id: uuid.UUID,
        user_id: uuid.UUID,
        source: FoodSource,
        meal_slot: MealSlot,
        planned_for: datetime,
        correlation_id: str,
    ) -> tuple[MealPlanEntry, DomainEvent]:
        entry = cls(plan_entry_id=plan_entry_id)
        event = build_meal_planned_event(
            plan_entry_id=plan_entry_id,
            user_id=user_id,
            source=source,
            meal_slot=meal_slot,
            planned_for=planned_for,
            correlation_id=correlation_id,
        )
        entry.apply(event)
        return entry, event

    def update(
        self,
        source: FoodSource,
        meal_slot: MealSlot,
        planned_for: datetime,
        updated_at: datetime,
        correlation_id: str,
    ) -> DomainEvent:
        if self.removed:
            raise PlanEntryAlreadyRemovedError("Cannot update a removed meal plan entry.")
        assert self.user_id is not None
        event = build_meal_plan_updated_event(
            plan_entry_id=self.plan_entry_id,
            user_id=self.user_id,
            source=source,
            meal_slot=meal_slot,
            planned_for=planned_for,
            updated_at=updated_at,
            correlation_id=correlation_id,
        )
        self.apply(event)
        return event

    def remove(self, removed_at: datetime, correlation_id: str) -> DomainEvent:
        if self.removed:
            raise PlanEntryAlreadyRemovedError("Meal plan entry is already removed.")
        assert self.user_id is not None
        event = build_meal_plan_removed_event(
            plan_entry_id=self.plan_entry_id,
            user_id=self.user_id,
            removed_at=removed_at,
            correlation_id=correlation_id,
        )
        self.apply(event)
        return event
