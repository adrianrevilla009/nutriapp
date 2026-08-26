"""NutrientTotalLine and MacroAmounts -- the canonical, per-line nutrient
total shape shared by both an entry-level and a day-level total
(nutrient_total_calculator.py builds these; daily_nutrition_total.py
accumulates them).

Canonical macro vocabulary (this service's own, per implementation plan
section 6(g) -- matches diary-service's `macros_per_unit` naming, since
macros are always sourced from diary's snapshot, never recomputed from
catalog-service's differently-named fields):
  calories_kcal, protein_g, carbs_g, fat_g.

Canonical micronutrient vocabulary matches catalog-service's
`nutrition_per_100g` micro field names (the only source of micronutrient
data): sugars_g, fiber_g, saturated_fat_g, sodium_mg, salt_g, calcium_mg,
iron_mg, vitamin_c_mg.

`micronutrients_status`:
  - "available": a catalog-product mirror match was found and its panel
    (however incomplete field-by-field) was joined in.
  - "unavailable": no mirror match yet, or a non-catalog source
    (never estimated/zeroed -- domain-calculation-conventions SKILL.md and
    the nutrition-calculation-agent's "never invent a value" rule).
  - "partial": day-level only -- some, not all, contributing entries
    resolved micronutrients.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

MicronutrientStatus = Literal["available", "partial", "unavailable"]


@dataclass(frozen=True, slots=True)
class MacroAmounts:
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float

    def __add__(self, other: MacroAmounts) -> MacroAmounts:
        return MacroAmounts(
            calories_kcal=self.calories_kcal + other.calories_kcal,
            protein_g=self.protein_g + other.protein_g,
            carbs_g=self.carbs_g + other.carbs_g,
            fat_g=self.fat_g + other.fat_g,
        )


ZERO_MACROS = MacroAmounts(calories_kcal=0.0, protein_g=0.0, carbs_g=0.0, fat_g=0.0)


@dataclass(frozen=True, slots=True)
class NutrientTotalLine:
    macros: MacroAmounts
    micronutrients: Mapping[str, float | None] | None
    micronutrients_status: MicronutrientStatus
    is_estimated: bool = False
