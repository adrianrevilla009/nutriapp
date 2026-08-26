"""DeleteFoodEntryCommand + handler."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from application.errors import FoodEntryAccessDeniedError, FoodEntryNotFoundError
from domain.entities.food_entry import FoodEntry
from domain.ports.event_store_port import EventStorePort
from domain.ports.outbox_repository_port import OutboxRepositoryPort

AGGREGATE_TYPE = "food_entry"


@dataclass(frozen=True, slots=True)
class DeleteFoodEntryCommand:
    entry_id: uuid.UUID
    user_id: uuid.UUID
    correlation_id: str


@dataclass(frozen=True, slots=True)
class DeleteFoodEntryResult:
    entry_id: uuid.UUID
    deleted: bool


class DeleteFoodEntryHandler:
    def __init__(
        self,
        event_store: EventStorePort,
        outbox: OutboxRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._event_store = event_store
        self._outbox = outbox
        self._now_fn = now_fn

    async def handle(self, command: DeleteFoodEntryCommand) -> DeleteFoodEntryResult:
        events = await self._event_store.load(AGGREGATE_TYPE, str(command.entry_id))
        if not events:
            raise FoodEntryNotFoundError(f"No food entry {command.entry_id} exists.")
        entry = FoodEntry.rebuild(events)
        if entry.user_id != command.user_id:
            raise FoodEntryAccessDeniedError("This food entry belongs to another user.")

        event = entry.delete(deleted_at=self._now_fn(), correlation_id=command.correlation_id)
        await self._event_store.append(AGGREGATE_TYPE, event, expected_version=len(events))
        await self._outbox.enqueue(event)
        return DeleteFoodEntryResult(entry_id=command.entry_id, deleted=True)
