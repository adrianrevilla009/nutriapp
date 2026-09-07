"""HandleNutrientDeficiencyDetectedHandler -- projects analytics-service's
NutrientDeficiencyDetected into analytics_signals. The event's `disclaimer`
field is stored and later surfaced VERBATIM -- this handler applies no
string transformation to it whatsoever (implementation plan section 5).
Idempotent by event_id."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.ports.analytics_signals_repository_port import AnalyticsSignalsRepositoryPort
from domain.ports.processed_analytics_events_repository_port import (
    ProcessedAnalyticsEventsRepositoryPort,
)


@dataclass(frozen=True, slots=True)
class HandleNutrientDeficiencyDetectedCommand:
    event_id: uuid.UUID
    user_id: uuid.UUID
    signal: str
    summary: str
    disclaimer: str


class HandleNutrientDeficiencyDetectedHandler:
    def __init__(
        self,
        processed_events: ProcessedAnalyticsEventsRepositoryPort,
        analytics_signals: AnalyticsSignalsRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._analytics_signals = analytics_signals

    async def handle(self, command: HandleNutrientDeficiencyDetectedCommand) -> None:
        if await self._processed_events.already_processed(command.event_id):
            return

        await self._analytics_signals.upsert_deficiency_signal(
            user_id=command.user_id,
            signal=command.signal,
            summary=command.summary,
            disclaimer=command.disclaimer,  # verbatim, never re-worded
        )
        await self._processed_events.mark_processed(command.event_id)
