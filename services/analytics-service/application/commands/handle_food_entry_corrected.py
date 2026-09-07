"""HandleFoodEntryCorrectedHandler -- `FoodEntryCorrected` replaces (not
adds to) the entry's contribution: the repository's `correct_food_entry`
reverses whatever this `entry_id` last contributed (via the adapter's own
internal ledger, see `daily_log_summary_repository_port.py`'s docstring)
and applies the new snapshot in one step -- correctly handling a
correction that also moves the entry to a different `on_date`."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from domain.ports.daily_log_summary_repository_port import DailyLogSummaryRepositoryPort
from domain.ports.processed_diary_events_repository_port import (
    ProcessedDiaryEventsRepositoryPort,
)


@dataclass(frozen=True, slots=True)
class HandleFoodEntryCorrectedCommand:
    event_id: uuid.UUID
    entry_id: uuid.UUID
    user_id: uuid.UUID
    quantity: float
    calories_kcal_per_unit: float
    protein_g_per_unit: float
    carbs_g_per_unit: float
    fat_g_per_unit: float
    occurred_at: datetime


class HandleFoodEntryCorrectedHandler:
    def __init__(
        self,
        processed_events: ProcessedDiaryEventsRepositoryPort,
        daily_log_summary: DailyLogSummaryRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._daily_log_summary = daily_log_summary

    async def handle(self, command: HandleFoodEntryCorrectedCommand) -> None:
        if await self._processed_events.is_processed(command.event_id):
            return

        on_date: date = command.occurred_at.date()
        await self._daily_log_summary.correct_food_entry(
            entry_id=command.entry_id,
            user_id=command.user_id,
            on_date=on_date,
            calories_kcal=command.quantity * command.calories_kcal_per_unit,
            protein_g=command.quantity * command.protein_g_per_unit,
            carbs_g=command.quantity * command.carbs_g_per_unit,
            fat_g=command.quantity * command.fat_g_per_unit,
        )
        await self._processed_events.mark_processed(command.event_id)
