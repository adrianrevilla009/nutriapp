"""RemoveMealPlanCommand + handler."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from application.errors import MealPlanAccessDeniedError, MealPlanEntryNotFoundError
from domain.entities.meal_plan_entry import MealPlanEntry
from domain.ports.event_store_port import EventStorePort
from domain.ports.outbox_repository_port import OutboxRepositoryPort

AGGREGATE_TYPE = "meal_plan_entry"


@dataclass(frozen=True, slots=True)
class RemoveMealPlanCommand:
    plan_entry_id: uuid.UUID
    user_id: uuid.UUID
    correlation_id: str


@dataclass(frozen=True, slots=True)
class RemoveMealPlanResult:
    plan_entry_id: uuid.UUID
    removed: bool


class RemoveMealPlanHandler:
    def __init__(
        self,
        event_store: EventStorePort,
        outbox: OutboxRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._event_store = event_store
        self._outbox = outbox
        self._now_fn = now_fn

    async def handle(self, command: RemoveMealPlanCommand) -> RemoveMealPlanResult:
        events = await self._event_store.load(AGGREGATE_TYPE, str(command.plan_entry_id))
        if not events:
            raise MealPlanEntryNotFoundError(f"No meal plan entry {command.plan_entry_id} exists.")
        entry = MealPlanEntry.rebuild(events)
        if entry.user_id != command.user_id:
            raise MealPlanAccessDeniedError("This meal plan entry belongs to another user.")

        event = entry.remove(removed_at=self._now_fn(), correlation_id=command.correlation_id)
        await self._event_store.append(AGGREGATE_TYPE, event, expected_version=len(events))
        await self._outbox.enqueue(event)
        return RemoveMealPlanResult(plan_entry_id=command.plan_entry_id, removed=True)
