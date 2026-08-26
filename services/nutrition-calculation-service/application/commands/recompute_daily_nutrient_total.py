"""RecomputeDailyNutrientTotalCommand -- triggered by
`RabbitMqDiaryFoodEntryConsumer` on `FoodEntryLogged`/`FoodEntryCorrected`/
`FoodEntryDeleted` (implementation plan section 1, acceptance criterion 3).

Idempotent by construction at the storage layer (implementation plan
acceptance criterion 4): the underlying `DailyNutritionTotal` entity keys
each contribution by `entry_id`, so replaying the same `FoodEntryLogged`
twice upserts the identical line twice rather than double-counting --
consumer-level dedup (`ProcessedEventsPort`) is a second, independent
backstop, not the only guarantee.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone

from domain.entities.daily_nutrition_total import DailyNutritionTotal
from domain.events.nutrition_value_recomputed import build_nutrition_value_recomputed_event
from domain.ports.daily_nutrition_total_repository_port import DailyNutritionTotalRepositoryPort
from domain.ports.nutrient_panel_mirror_port import NutrientPanelMirrorPort
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.services.nutrient_total_calculator import (
    CATALOG_PRODUCT_SOURCE_TYPE,
    calculate_entry_nutrient_total,
)
from domain.services.recomputation_policy import total_recompute_reason_for
from domain.value_objects.formula_version import CURRENT_FORMULA_VERSION

FOOD_ENTRY_DELETED = "FoodEntryDeleted"


@dataclass(frozen=True, slots=True)
class RecomputeDailyNutrientTotalCommand:
    user_id: uuid.UUID
    entry_id: uuid.UUID
    total_date: date
    trigger_event_type: str
    correlation_id: str
    quantity_grams: float | None = None
    macros_per_unit: Mapping[str, float] | None = None
    source_type: str | None = None
    source_reference_id: str | None = None


class RecomputeDailyNutrientTotalHandler:
    def __init__(
        self,
        totals_repository: DailyNutritionTotalRepositoryPort,
        mirror_port: NutrientPanelMirrorPort,
        outbox_repository: OutboxRepositoryPort,
    ) -> None:
        self._totals_repository = totals_repository
        self._mirror_port = mirror_port
        self._outbox_repository = outbox_repository

    async def handle(self, command: RecomputeDailyNutrientTotalCommand) -> DailyNutritionTotal:
        existing = await self._totals_repository.get(command.user_id, command.total_date)
        current = existing or DailyNutritionTotal(
            user_id=command.user_id, total_date=command.total_date
        )

        if command.trigger_event_type == FOOD_ENTRY_DELETED:
            new_total = current.with_entry_removed(command.entry_id)
        else:
            assert command.macros_per_unit is not None, (
                "macros_per_unit required for a logged/corrected entry"
            )
            assert command.source_type is not None, (
                "source_type required for a logged/corrected entry"
            )
            assert command.quantity_grams is not None, (
                "quantity_grams required for a logged/corrected entry"
            )
            panel = None
            if command.source_type == CATALOG_PRODUCT_SOURCE_TYPE and command.source_reference_id:
                panel = await self._mirror_port.get_by_reference_id(command.source_reference_id)
            line = calculate_entry_nutrient_total(
                quantity_grams=command.quantity_grams,
                macros_per_unit=command.macros_per_unit,
                source_type=command.source_type,
                micronutrient_panel_per_100g=panel,
            )
            new_total = current.with_entry_upserted(command.entry_id, line)

        await self._totals_repository.upsert(new_total)

        day_line = new_total.compute_total()
        reason = total_recompute_reason_for(command.trigger_event_type)
        event = build_nutrition_value_recomputed_event(
            user_id=command.user_id,
            scope="day",
            entry_id=None,
            total_date=command.total_date,
            line=day_line,
            confidence_range=None,
            formula_version=CURRENT_FORMULA_VERSION,
            reason=reason,  # type: ignore[arg-type]
            correlation_id=command.correlation_id,
            recomputed_at=datetime.now(timezone.utc),
        )
        await self._outbox_repository.enqueue(event)
        return new_total
