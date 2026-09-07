"""HandleWaterIntakeRemovedHandler -- removes the intake's projected row.
Idempotent: a duplicate delivery must never double-remove/error."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.ports.diary_history_repository_port import DiaryHistoryRepositoryPort
from domain.ports.processed_diary_events_repository_port import (
    ProcessedDiaryEventsRepositoryPort,
)


@dataclass(frozen=True, slots=True)
class HandleWaterIntakeRemovedCommand:
    event_id: uuid.UUID
    intake_id: uuid.UUID


class HandleWaterIntakeRemovedHandler:
    def __init__(
        self,
        processed_events: ProcessedDiaryEventsRepositoryPort,
        diary_history: DiaryHistoryRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._diary_history = diary_history

    async def handle(self, command: HandleWaterIntakeRemovedCommand) -> None:
        if await self._processed_events.already_processed(command.event_id):
            return

        await self._diary_history.remove_water_intake(command.intake_id)
        await self._processed_events.mark_processed(command.event_id)
