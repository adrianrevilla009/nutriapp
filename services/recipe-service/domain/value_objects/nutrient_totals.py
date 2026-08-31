"""MacroAmounts / NutrientTotals / RecipeNutrientTotals -- the canonical
nutrient-total shapes this service computes for a Recipe.

Mirrors `nutrition-calculation-service`'s `MacroAmounts`/
`NutrientTotalLine`/`MicronutrientStatus` shape field-for-field
(implementation plan section 1: "mirrors the same formula, don't import
code" -- CLAUDE.md section 2.5 forbids a cross-service domain-layer
import, so this is `recipe-service`'s own, independent copy).

Canonical macro vocabulary (matches nutrition-calculation-service's own):
  calories_kcal, protein_g, carbs_g, fat_g.

Canonical micronutrient vocabulary matches `NutrientPanel`'s (which itself
matches catalog-service's `nutrition_per_100g` field names): sugars_g,
fiber_g, saturated_fat_g, sodium_mg, salt_g, calcium_mg, iron_mg,
vitamin_c_mg.

`micronutrients_status`:
  - "available": the source ingredient's `nutrition_per_100g` panel was
    present (however incomplete field-by-field).
  - "unavailable": no ingredient contributed micronutrient data (a
    recipe with zero ingredients, or every ingredient's catalog product
    has no nutrition panel).
  - "partial": recipe-level only -- some, not all, ingredients resolved
    micronutrients.

`macros_status` mirrors `micronutrients_status` exactly, computed
independently over the same per-ingredient `nutrition_per_100g` presence
signal (recipe-agent.md follow-up, resolved: an ingredient with no
nutrition panel silently contributed zero to macro totals with no status
signal -- this field makes that visible the same way
`micronutrients_status` already does):
  - "available": every ingredient that contributed to this total had a
    `nutrition_per_100g` panel present (however incomplete field-by-field
    -- an individual null macro field, e.g. `energy_kcal` unknown for one
    product, still counts as "available" and scales to zero for that
    field only, same convention as micronutrients).
  - "unavailable": no ingredient contributed macro data (a recipe with
    zero ingredients, or every ingredient's catalog product has no
    nutrition panel).
  - "partial": recipe-level only -- some, not all, ingredients resolved
    macro data.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

MicronutrientStatus = Literal["available", "partial", "unavailable"]
MacroStatus = Literal["available", "partial", "unavailable"]


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
class NutrientTotals:
    macros: MacroAmounts
    macros_status: MacroStatus
    micronutrients: Mapping[str, float | None] | None
    micronutrients_status: MicronutrientStatus


@dataclass(frozen=True, slots=True)
class RecipeNutrientTotals:
    """Persisted on `Recipe.computed_totals` -- never accepted as user
    input, always derived by `recipe_nutrient_calculator.py` from the
    ingredient list (recipe-agent.md's explicit rule)."""

    per_recipe: NutrientTotals
    per_serving: NutrientTotals
