"""HandleNutritionValueRecomputedHandler -- projects NutritionValueRecomputed
(nutrition-calculation-service) into nutrition_history, keyed by the
event's own entry_id/date scope so a redelivery or a later recompute of
the same scope upserts in place rather than accumulating duplicate rows.
Idempotent by event_id, incremental (touches only the affected scope)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from domain.ports.nutrition_history_repository_port import NutritionHistoryRepositoryPort
from domain.ports.processed_nutrition_calculation_events_repository_port import (
    ProcessedNutritionCalculationEventsRepositoryPort,
)


@dataclass(frozen=True, slots=True)
class HandleNutritionValueRecomputedCommand:
    event_id: uuid.UUID
    user_id: uuid.UUID
    scope: str
    reference_id: str
    on_date: date | None
    summary: str


class HandleNutritionValueRecomputedHandler:
    def __init__(
        self,
        processed_events: ProcessedNutritionCalculationEventsRepositoryPort,
        nutrition_history: NutritionHistoryRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._nutrition_history = nutrition_history

    async def handle(self, command: HandleNutritionValueRecomputedCommand) -> None:
        if await self._processed_events.already_processed(command.event_id):
            return

        await self._nutrition_history.upsert_value_recomputed(
            user_id=command.user_id,
            scope=command.scope,
            reference_id=command.reference_id,
            on_date=command.on_date,
            summary=command.summary,
        )
        await self._processed_events.mark_processed(command.event_id)
