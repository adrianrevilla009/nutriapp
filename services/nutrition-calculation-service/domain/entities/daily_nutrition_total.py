"""DailyNutritionTotal -- the per-user-per-day nutrient total aggregate.

Conventional persistence (ADR-0002, not event-sourced): this is the
`daily_nutrition_totals` table's in-memory shape (one row, upsert by
`(user_id, date)`), not a fold over an event stream. It tracks each
contributing entry's own `NutrientTotalLine` (keyed by `entry_id`) so a
`FoodEntryCorrected` can replace a prior contribution in place, and a
`FoodEntryDeleted` can remove one entirely, without double-counting
(implementation plan acceptance criterion 4 -- idempotent recomputation).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from domain.services.nutrient_total_calculator import calculate_day_nutrient_total
from domain.value_objects.nutrient_total_line import NutrientTotalLine


@dataclass(frozen=True, slots=True)
class DailyNutritionTotal:
    user_id: uuid.UUID
    total_date: date
    entries: dict[uuid.UUID, NutrientTotalLine] = field(default_factory=dict)

    def with_entry_upserted(
        self, entry_id: uuid.UUID, line: NutrientTotalLine
    ) -> DailyNutritionTotal:
        new_entries = dict(self.entries)
        new_entries[entry_id] = line
        return DailyNutritionTotal(
            user_id=self.user_id, total_date=self.total_date, entries=new_entries
        )

    def with_entry_removed(self, entry_id: uuid.UUID) -> DailyNutritionTotal:
        new_entries = dict(self.entries)
        new_entries.pop(entry_id, None)
        return DailyNutritionTotal(
            user_id=self.user_id, total_date=self.total_date, entries=new_entries
        )

    def compute_total(self) -> NutrientTotalLine:
        return calculate_day_nutrient_total(self.entries.values())
