"""PlanMealCommand + handler."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from domain.entities.meal_plan_entry import MealPlanEntry
from domain.ports.event_store_port import EventStorePort
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.value_objects.food_source import FoodSource
from domain.value_objects.meal_slot import MealSlot

AGGREGATE_TYPE = "meal_plan_entry"


@dataclass(frozen=True, slots=True)
class PlanMealCommand:
    user_id: uuid.UUID
    source: FoodSource
    meal_slot: MealSlot
    planned_for: datetime
    correlation_id: str


@dataclass(frozen=True, slots=True)
class PlanMealResult:
    plan_entry_id: uuid.UUID
    source: FoodSource
    meal_slot: MealSlot
    planned_for: datetime


class PlanMealHandler:
    def __init__(
        self,
        event_store: EventStorePort,
        outbox: OutboxRepositoryPort,
        id_fn: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._event_store = event_store
        self._outbox = outbox
        self._id_fn = id_fn

    async def handle(self, command: PlanMealCommand) -> PlanMealResult:
        plan_entry_id = self._id_fn()
        _entry, event = MealPlanEntry.plan(
            plan_entry_id=plan_entry_id,
            user_id=command.user_id,
            source=command.source,
            meal_slot=command.meal_slot,
            planned_for=command.planned_for,
            correlation_id=command.correlation_id,
        )
        await self._event_store.append(AGGREGATE_TYPE, event, expected_version=0)
        await self._outbox.enqueue(event)
        return PlanMealResult(
            plan_entry_id=plan_entry_id,
            source=command.source,
            meal_slot=command.meal_slot,
            planned_for=command.planned_for,
        )
