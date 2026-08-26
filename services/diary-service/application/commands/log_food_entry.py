"""LogFoodEntryCommand + handler."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from domain.entities.food_entry import FoodEntry
from domain.ports.event_store_port import EventStorePort
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.value_objects.food_source import FoodSource
from domain.value_objects.meal_slot import MealSlot

AGGREGATE_TYPE = "food_entry"


@dataclass(frozen=True, slots=True)
class LogFoodEntryCommand:
    user_id: uuid.UUID
    source: FoodSource
    meal_slot: MealSlot
    occurred_at: datetime
    correlation_id: str


@dataclass(frozen=True, slots=True)
class LogFoodEntryResult:
    entry_id: uuid.UUID
    user_id: uuid.UUID
    source: FoodSource
    meal_slot: MealSlot
    occurred_at: datetime


class LogFoodEntryHandler:
    def __init__(
        self,
        event_store: EventStorePort,
        outbox: OutboxRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        id_fn: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._event_store = event_store
        self._outbox = outbox
        self._now_fn = now_fn
        self._id_fn = id_fn

    async def handle(self, command: LogFoodEntryCommand) -> LogFoodEntryResult:
        entry_id = self._id_fn()
        _entry, event = FoodEntry.log(
            entry_id=entry_id,
            user_id=command.user_id,
            source=command.source,
            meal_slot=command.meal_slot,
            occurred_at=command.occurred_at,
            correlation_id=command.correlation_id,
        )
        await self._event_store.append(AGGREGATE_TYPE, event, expected_version=0)
        await self._outbox.enqueue(event)
        return LogFoodEntryResult(
            entry_id=entry_id,
            user_id=command.user_id,
            source=command.source,
            meal_slot=command.meal_slot,
            occurred_at=command.occurred_at,
        )
