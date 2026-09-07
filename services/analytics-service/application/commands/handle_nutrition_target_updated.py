"""HandleNutritionTargetUpdatedHandler -- projects `NutritionTargetUpdated`
(nutrition-calculation-service) into this service's "current target"
reference per tracked nutrient (`domain.tracked_nutrients.TRACKED_NUTRIENTS`
-- see that module's docstring for the known micronutrient-coverage gap).

Only updates the CURRENT target used for future `micronutrient_window`
upserts -- never rewrites already-persisted historical rows (test-plan
section 2's explicit assertion: a later target change must not retroactively
alter what an earlier day's row recorded as the target in effect then)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.ports.micronutrient_window_repository_port import MicronutrientWindowRepositoryPort
from domain.ports.processed_nutrition_calculation_events_repository_port import (
    ProcessedNutritionCalculationEventsRepositoryPort,
)
from domain.tracked_nutrients import TRACKED_NUTRIENTS


@dataclass(frozen=True, slots=True)
class HandleNutritionTargetUpdatedCommand:
    event_id: uuid.UUID
    user_id: uuid.UUID
    protein_g_min: float | None
    fat_g_min: float | None


class HandleNutritionTargetUpdatedHandler:
    def __init__(
        self,
        processed_events: ProcessedNutritionCalculationEventsRepositoryPort,
        micronutrient_window: MicronutrientWindowRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._micronutrient_window = micronutrient_window

    async def handle(self, command: HandleNutritionTargetUpdatedCommand) -> None:
        if await self._processed_events.is_processed(command.event_id):
            return

        targets = {"protein_g": command.protein_g_min, "fat_g": command.fat_g_min}
        for nutrient in TRACKED_NUTRIENTS:
            await self._micronutrient_window.set_current_target_min(
                command.user_id, nutrient, targets.get(nutrient)
            )
        await self._processed_events.mark_processed(command.event_id)
