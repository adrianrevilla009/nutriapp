"""HandleNutritionTargetUpdatedHandler -- projects `NutritionTargetUpdated`
(nutrition-calculation-service) into this service's "current target"
reference per tracked nutrient (`domain.tracked_nutrients.TRACKED_NUTRIENTS`
-- see that module's docstring for the coverage history and the still-open
value-side gap).

`target_min_by_nutrient` is a generic, already-resolved nutrient-name-keyed
mapping (built by the infrastructure dispatch layer from
`NutritionTargetUpdated`'s `nutrient_targets_min` map, with a
`macro_targets`-sourced fallback for `protein_g`/`fat_g` for backward
compatibility with events published before `nutrient_targets_min` existed
-- see `infrastructure/messaging/nutrition_calculation_events_consumer.py`).
A missing/`None` entry for a given tracked nutrient means "no target
published for this user/nutrient" -- stored as `None`, never defaulted or
fabricated (addendum 2026-09-12).

Only updates the CURRENT target used for future `micronutrient_window`
upserts -- never rewrites already-persisted historical rows (test-plan
section 2's explicit assertion: a later target change must not retroactively
alter what an earlier day's row recorded as the target in effect then)."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field

from domain.ports.micronutrient_window_repository_port import MicronutrientWindowRepositoryPort
from domain.ports.processed_nutrition_calculation_events_repository_port import (
    ProcessedNutritionCalculationEventsRepositoryPort,
)
from domain.tracked_nutrients import TRACKED_NUTRIENTS


@dataclass(frozen=True, slots=True)
class HandleNutritionTargetUpdatedCommand:
    event_id: uuid.UUID
    user_id: uuid.UUID
    target_min_by_nutrient: Mapping[str, float | None] = field(default_factory=dict)


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

        for nutrient in TRACKED_NUTRIENTS:
            await self._micronutrient_window.set_current_target_min(
                command.user_id, nutrient, command.target_min_by_nutrient.get(nutrient)
            )
        await self._processed_events.mark_processed(command.event_id)
