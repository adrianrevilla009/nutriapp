"""HandleWaterIntakeLoggedHandler -- projects `WaterIntakeLogged`
(diary-service) into `daily_log_summary` via `apply_water_intake`.
Idempotent by `event_id`."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from domain.ports.daily_log_summary_repository_port import DailyLogSummaryRepositoryPort
from domain.ports.processed_diary_events_repository_port import (
    ProcessedDiaryEventsRepositoryPort,
)


@dataclass(frozen=True, slots=True)
class HandleWaterIntakeLoggedCommand:
    event_id: uuid.UUID
    intake_id: uuid.UUID
    user_id: uuid.UUID
    amount_ml: float
    occurred_at: datetime


class HandleWaterIntakeLoggedHandler:
    def __init__(
        self,
        processed_events: ProcessedDiaryEventsRepositoryPort,
        daily_log_summary: DailyLogSummaryRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._daily_log_summary = daily_log_summary

    async def handle(self, command: HandleWaterIntakeLoggedCommand) -> None:
        if await self._processed_events.is_processed(command.event_id):
            return

        on_date: date = command.occurred_at.date()
        await self._daily_log_summary.apply_water_intake(
            intake_id=command.intake_id,
            user_id=command.user_id,
            on_date=on_date,
            amount_ml=command.amount_ml,
        )
        await self._processed_events.mark_processed(command.event_id)
