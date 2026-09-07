"""HandleFoodEntryDeletedHandler -- `FoodEntryDeleted` carries no macro
data (docs/events-catalog.md), so reversal relies entirely on the
repository adapter's own ledger (`remove_food_entry`, see
`daily_log_summary_repository_port.py`'s docstring). Subtracts the
entry's last-known contribution -- never zeroes the whole day."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.ports.daily_log_summary_repository_port import DailyLogSummaryRepositoryPort
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
        daily_log_summary: DailyLogSummaryRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._daily_log_summary = daily_log_summary

    async def handle(self, command: HandleFoodEntryDeletedCommand) -> None:
        if await self._processed_events.is_processed(command.event_id):
            return

        await self._daily_log_summary.remove_food_entry(command.entry_id)
        await self._processed_events.mark_processed(command.event_id)
