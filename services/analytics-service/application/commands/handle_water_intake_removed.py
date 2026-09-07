"""HandleWaterIntakeRemovedHandler -- `WaterIntakeRemoved` carries no
`amount_ml` (docs/events-catalog.md), so reversal relies on the
repository adapter's own ledger (`remove_water_intake`). Subtracts
exactly what that intake entry contributed -- never double-subtracts on
a redelivered event (test-plan section 2's explicit assertion)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.ports.daily_log_summary_repository_port import DailyLogSummaryRepositoryPort
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
        daily_log_summary: DailyLogSummaryRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._daily_log_summary = daily_log_summary

    async def handle(self, command: HandleWaterIntakeRemovedCommand) -> None:
        if await self._processed_events.is_processed(command.event_id):
            return

        await self._daily_log_summary.remove_water_intake(command.intake_id)
        await self._processed_events.mark_processed(command.event_id)
