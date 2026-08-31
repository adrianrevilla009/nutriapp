"""Recipe nutrient calculator -- per-ingredient, per-recipe, and
per-serving nutrient totals (domain-calculation-conventions SKILL.md
section 2, implementation plan section 1 acceptance criterion 1, mirrors
`nutrition-calculation-service`'s `nutrient_total_calculator.py` formula
exactly, own independent copy per CLAUDE.md section 2.5):

  nutrient_amount = (per_100g_value / 100) x quantity_grams

Unlike `nutrition-calculation-service` (whose macros come from
diary-service's snapshot and whose micronutrients come from a separate
local mirror), `recipe-service` sources BOTH macro and micro figures from
the same `catalog-service` `nutrition_per_100g` panel per ingredient --
there is only one source of truth per ingredient, resolved via
`CatalogProductPort`.

Field-name translation (this service's own anticorruption layer, not a
formula difference): the catalog panel's `energy_kcal`/`carbohydrates_g`
map onto this service's canonical `calories_kcal`/`carbs_g` macro names
(matching `nutrition-calculation-service`'s vocabulary so the two
services' totals are directly comparable); `protein_g`/`fat_g` pass
through unchanged. The eight micronutrient fields pass through unchanged.

Resolved ambiguity (flagged in the final implementation report, not fully
spelled out in the test plan): when an ingredient's catalog product has NO
nutrition panel at all (`nutrition_per_100g is None`), that ingredient
contributes ZERO to the recipe's macro totals (never estimated/invented --
domain-calculation-conventions SKILL.md's "never invent a value") in
addition to being excluded from the micronutrient merge and marked
"unavailable" for that ingredient. This under-counts the true macro total
for a recipe with a data-incomplete ingredient rather than blocking
computation entirely; `micronutrients_status` (partial/unavailable) is the
signal surfaced to the caller that the totals may be incomplete.

Follow-up resolved (architecture-agent/reviewer-agent flag from the prior
review pass): `macros_status` mirrors `micronutrients_status` exactly --
same "available"/"partial"/"unavailable" computation over the same
per-ingredient `nutrition_per_100g`-presence signal, independently applied
at both the per-recipe and per-serving level -- so a caller can no longer
mistake a silently-undercounted macro total for a complete one.
"""

from __future__ import annotations

from collections.abc import Iterable

from domain.value_objects.nutrient_panel import NutrientPanel
from domain.value_objects.nutrient_totals import (
    ZERO_MACROS,
    MacroAmounts,
    MicronutrientStatus,
    NutrientTotals,
    RecipeNutrientTotals,
)


def _scale(value: float | None, quantity_grams: float) -> float:
    if value is None:
        return 0.0
    return (value / 100.0) * quantity_grams


def calculate_ingredient_nutrient_total(
    *, quantity_grams: float, nutrition_per_100g: NutrientPanel | None
) -> NutrientTotals:
    if nutrition_per_100g is None:
        return NutrientTotals(
            macros=ZERO_MACROS,
            macros_status="unavailable",
            micronutrients=None,
            micronutrients_status="unavailable",
        )

    macros = MacroAmounts(
        calories_kcal=_scale(nutrition_per_100g.energy_kcal, quantity_grams),
        protein_g=_scale(nutrition_per_100g.protein_g, quantity_grams),
        carbs_g=_scale(nutrition_per_100g.carbohydrates_g, quantity_grams),
        fat_g=_scale(nutrition_per_100g.fat_g, quantity_grams),
    )
    micronutrients = {
        field: (_scale(value, quantity_grams) if value is not None else None)
        for field, value in nutrition_per_100g.micronutrient_values().items()
    }
    return NutrientTotals(
        macros=macros,
        macros_status="available",
        micronutrients=micronutrients,
        micronutrients_status="available",
    )


def _aggregate_status(statuses: set[MicronutrientStatus]) -> MicronutrientStatus:
    """Shared "available"/"partial"/"unavailable" aggregation rule --
    identical for `macros_status` and `micronutrients_status` (same
    per-ingredient `nutrition_per_100g`-presence signal, CLAUDE.md
    section 2.5's "never invent a value" applies equally to both).
    `MacroStatus` and `MicronutrientStatus` are the same literal value set
    (see `nutrient_totals.py`), so this one helper aggregates both."""
    if statuses == {"available"}:
        return "available"
    if statuses == {"unavailable"}:
        return "unavailable"
    return "partial"


def _merge_micronutrients(lines: Iterable[NutrientTotals]) -> dict[str, float | None] | None:
    merged: dict[str, float | None] = {}
    any_available = False
    for line in lines:
        if line.micronutrients_status != "available" or line.micronutrients is None:
            continue
        any_available = True
        for field, value in line.micronutrients.items():
            if value is None:
                merged.setdefault(field, None)
                continue
            current = merged.get(field)
            merged[field] = value if current is None else current + value
    return merged if any_available else None


def _divide(total: NutrientTotals, servings: int) -> NutrientTotals:
    macros = MacroAmounts(
        calories_kcal=total.macros.calories_kcal / servings,
        protein_g=total.macros.protein_g / servings,
        carbs_g=total.macros.carbs_g / servings,
        fat_g=total.macros.fat_g / servings,
    )
    micronutrients = (
        {
            field: (value / servings if value is not None else None)
            for field, value in total.micronutrients.items()
        }
        if total.micronutrients is not None
        else None
    )
    return NutrientTotals(
        macros=macros,
        macros_status=total.macros_status,
        micronutrients=micronutrients,
        micronutrients_status=total.micronutrients_status,
    )


def calculate_recipe_nutrient_totals(
    ingredient_lines: Iterable[NutrientTotals], servings: int
) -> RecipeNutrientTotals:
    """`ingredient_lines` -- one `NutrientTotals` per ingredient (already
    scaled by that ingredient's quantity via
    `calculate_ingredient_nutrient_total`). Zero ingredients -> zero
    totals, never a division error (`servings` is always a positive int,
    enforced by the `Servings` value object at the caller)."""
    lines = list(ingredient_lines)

    if not lines:
        per_recipe = NutrientTotals(
            macros=ZERO_MACROS,
            macros_status="unavailable",
            micronutrients=None,
            micronutrients_status="unavailable",
        )
    else:
        macros = ZERO_MACROS
        for line in lines:
            macros = macros + line.macros

        macros_status = _aggregate_status({line.macros_status for line in lines})
        status = _aggregate_status({line.micronutrients_status for line in lines})

        micronutrients = _merge_micronutrients(lines) if status != "unavailable" else None
        per_recipe = NutrientTotals(
            macros=macros,
            macros_status=macros_status,
            micronutrients=micronutrients,
            micronutrients_status=status,
        )

    per_serving = _divide(per_recipe, servings)
    return RecipeNutrientTotals(per_recipe=per_recipe, per_serving=per_serving)
