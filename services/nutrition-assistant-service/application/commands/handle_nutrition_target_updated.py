"""HandleNutritionTargetUpdatedHandler -- projects NutritionTargetUpdated
(nutrition-calculation-service) into the user's current-target summary row
in nutrition_history. Idempotent by event_id."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.ports.nutrition_history_repository_port import NutritionHistoryRepositoryPort
from domain.ports.processed_nutrition_calculation_events_repository_port import (
    ProcessedNutritionCalculationEventsRepositoryPort,
)


@dataclass(frozen=True, slots=True)
class HandleNutritionTargetUpdatedCommand:
    event_id: uuid.UUID
    user_id: uuid.UUID
    summary: str


class HandleNutritionTargetUpdatedHandler:
    def __init__(
        self,
        processed_events: ProcessedNutritionCalculationEventsRepositoryPort,
        nutrition_history: NutritionHistoryRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._nutrition_history = nutrition_history

    async def handle(self, command: HandleNutritionTargetUpdatedCommand) -> None:
        if await self._processed_events.already_processed(command.event_id):
            return

        await self._nutrition_history.upsert_target_updated(
            user_id=command.user_id, summary=command.summary
        )
        await self._processed_events.mark_processed(command.event_id)
