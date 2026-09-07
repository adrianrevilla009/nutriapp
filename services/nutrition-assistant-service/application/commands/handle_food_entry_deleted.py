"""HandleFoodEntryDeletedHandler -- removes the entry's projected row.
Idempotent (a second delivery finds nothing to remove -- the repository's
remove_food_entry is itself an idempotent no-op on a missing row)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.ports.diary_history_repository_port import DiaryHistoryRepositoryPort
from domain.ports.processed_diary_events_repository_port import (
    ProcessedDiaryEventsRepositoryPort,
)


@dataclass(frozen=True, slots=True)
class HandleFoodEntryDeletedCommand:
    event_id: uuid.UUID
    entry_id: uuid.UUID


class HandleFoodEntryDeletedHandler:
    def __init__(
        self,
        processed_events: ProcessedDiaryEventsRepositoryPort,
        diary_history: DiaryHistoryRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._diary_history = diary_history

    async def handle(self, command: HandleFoodEntryDeletedCommand) -> None:
        if await self._processed_events.already_processed(command.event_id):
            return

        await self._diary_history.remove_food_entry(command.entry_id)
        await self._processed_events.mark_processed(command.event_id)
