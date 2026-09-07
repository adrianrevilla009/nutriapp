"""HandleWaterIntakeLoggedHandler -- projects WaterIntakeLogged
(diary-service) into diary_history. Idempotent, incremental (touches only
the single affected intake_id)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.ports.diary_history_repository_port import DiaryHistoryRepositoryPort
from domain.ports.processed_diary_events_repository_port import (
    ProcessedDiaryEventsRepositoryPort,
)


@dataclass(frozen=True, slots=True)
class HandleWaterIntakeLoggedCommand:
    event_id: uuid.UUID
    intake_id: uuid.UUID
    user_id: uuid.UUID
    summary: str
    occurred_at: datetime


class HandleWaterIntakeLoggedHandler:
    def __init__(
        self,
        processed_events: ProcessedDiaryEventsRepositoryPort,
        diary_history: DiaryHistoryRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._diary_history = diary_history

    async def handle(self, command: HandleWaterIntakeLoggedCommand) -> None:
        if await self._processed_events.already_processed(command.event_id):
            return

        await self._diary_history.upsert_water_intake(
            intake_id=command.intake_id,
            user_id=command.user_id,
            summary=command.summary,
            occurred_at=command.occurred_at,
        )
        await self._processed_events.mark_processed(command.event_id)
