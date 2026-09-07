"""HandleFoodEntryCorrectedHandler -- FoodEntryCorrected replaces the
entry's prior projected summary (full replacement, per diary-service's own
"corrections are new events, never edits to history" convention -- this
service's *projection* of the current state is what's replaced, not the
diary-service event history itself). Idempotent, incremental."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.ports.diary_history_repository_port import DiaryHistoryRepositoryPort
from domain.ports.processed_diary_events_repository_port import (
    ProcessedDiaryEventsRepositoryPort,
)


@dataclass(frozen=True, slots=True)
class HandleFoodEntryCorrectedCommand:
    event_id: uuid.UUID
    entry_id: uuid.UUID
    user_id: uuid.UUID
    summary: str
    occurred_at: datetime


class HandleFoodEntryCorrectedHandler:
    def __init__(
        self,
        processed_events: ProcessedDiaryEventsRepositoryPort,
        diary_history: DiaryHistoryRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._diary_history = diary_history

    async def handle(self, command: HandleFoodEntryCorrectedCommand) -> None:
        if await self._processed_events.already_processed(command.event_id):
            return

        await self._diary_history.upsert_food_entry(
            entry_id=command.entry_id,
            user_id=command.user_id,
            summary=command.summary,
            occurred_at=command.occurred_at,
        )
        await self._processed_events.mark_processed(command.event_id)
