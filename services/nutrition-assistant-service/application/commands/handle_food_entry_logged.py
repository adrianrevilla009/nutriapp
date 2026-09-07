"""HandleFoodEntryLoggedHandler -- projects FoodEntryLogged (diary-service)
into diary_history via the repository's entry-oriented upsert_food_entry.
Idempotent by event_id. Incremental: touches only the single affected
entry_id, never rewrites the user's full history
(.claude/agents/nutrition-assistant-agent.md)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.ports.diary_history_repository_port import DiaryHistoryRepositoryPort
from domain.ports.processed_diary_events_repository_port import (
    ProcessedDiaryEventsRepositoryPort,
)


@dataclass(frozen=True, slots=True)
class HandleFoodEntryLoggedCommand:
    event_id: uuid.UUID
    entry_id: uuid.UUID
    user_id: uuid.UUID
    summary: str
    occurred_at: datetime


class HandleFoodEntryLoggedHandler:
    def __init__(
        self,
        processed_events: ProcessedDiaryEventsRepositoryPort,
        diary_history: DiaryHistoryRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._diary_history = diary_history

    async def handle(self, command: HandleFoodEntryLoggedCommand) -> None:
        if await self._processed_events.already_processed(command.event_id):
            return

        await self._diary_history.upsert_food_entry(
            entry_id=command.entry_id,
            user_id=command.user_id,
            summary=command.summary,
            occurred_at=command.occurred_at,
        )
        await self._processed_events.mark_processed(command.event_id)
