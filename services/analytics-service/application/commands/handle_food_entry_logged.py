"""HandleFoodEntryLoggedHandler -- projects `FoodEntryLogged` (diary-service)
into `daily_log_summary` via the repository's entry-oriented
`apply_food_entry`. Contribution = `quantity * macros_per_unit` from the
event's own client-supplied snapshot (diary-service's documented scoping
decision -- this service never calls back to catalog-service to validate
it, same trust boundary diary-service itself uses).

Idempotent by `event_id` (messaging-conventions SKILL.md): a redelivered
event must never double-apply a contribution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from domain.ports.daily_log_summary_repository_port import DailyLogSummaryRepositoryPort
from domain.ports.processed_diary_events_repository_port import (
    ProcessedDiaryEventsRepositoryPort,
)


@dataclass(frozen=True, slots=True)
class HandleFoodEntryLoggedCommand:
    event_id: uuid.UUID
    entry_id: uuid.UUID
    user_id: uuid.UUID
    quantity: float
    calories_kcal_per_unit: float
    protein_g_per_unit: float
    carbs_g_per_unit: float
    fat_g_per_unit: float
    occurred_at: datetime


class HandleFoodEntryLoggedHandler:
    def __init__(
        self,
        processed_events: ProcessedDiaryEventsRepositoryPort,
        daily_log_summary: DailyLogSummaryRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._daily_log_summary = daily_log_summary

    async def handle(self, command: HandleFoodEntryLoggedCommand) -> None:
        if await self._processed_events.is_processed(command.event_id):
            return

        on_date: date = command.occurred_at.date()
        await self._daily_log_summary.apply_food_entry(
            entry_id=command.entry_id,
            user_id=command.user_id,
            on_date=on_date,
            calories_kcal=command.quantity * command.calories_kcal_per_unit,
            protein_g=command.quantity * command.protein_g_per_unit,
            carbs_g=command.quantity * command.carbs_g_per_unit,
            fat_g=command.quantity * command.fat_g_per_unit,
        )
        await self._processed_events.mark_processed(command.event_id)
