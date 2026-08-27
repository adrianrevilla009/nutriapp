"""Nutrient total calculator -- per-entry and per-day nutrient totals
(domain-calculation-conventions SKILL.md section 2, implementation plan
section 1, acceptance criterion 1):

  nutrient_amount = (per_100g_value / 100) x quantity_grams

Macros always come from diary-service's own `FoodEntryLogged`/
`FoodEntryCorrected` snapshot (`source.snapshot.macros_per_unit`) -- never
a synchronous catalog-service lookup (settled scoping decision,
implementation plan section 1). Micronutrients are joined from this
service's local, denormalized `nutrient_panel_mirror` only when
`source_type == "catalog_product"`, keyed by `source_reference_id`. When
there is no mirror match yet (an accepted, eventually-consistent gap,
implementation plan section 6(b)) the micronutrient portion is marked
"unavailable" explicitly -- never estimated or zeroed.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from domain.value_objects.nutrient_total_line import (
    ZERO_MACROS,
    MacroAmounts,
    MicronutrientStatus,
    NutrientTotalLine,
)

CATALOG_PRODUCT_SOURCE_TYPE = "catalog_product"


def _scale(per_100g_value: float, quantity_grams: float) -> float:
    return (per_100g_value / 100.0) * quantity_grams


def calculate_entry_nutrient_total(
    *,
    quantity_grams: float,
    macros_per_unit: Mapping[str, float],
    source_type: str,
    micronutrient_panel_per_100g: Mapping[str, float | None] | None,
) -> NutrientTotalLine:
    """`macros_per_unit` is diary-service's already-canonical per-100g macro
    shape (calories_kcal/protein_g/carbs_g/fat_g); scaled by quantity here.
    """
    macros = MacroAmounts(
        calories_kcal=_scale(macros_per_unit["calories_kcal"], quantity_grams),
        protein_g=_scale(macros_per_unit["protein_g"], quantity_grams),
        carbs_g=_scale(macros_per_unit["carbs_g"], quantity_grams),
        fat_g=_scale(macros_per_unit["fat_g"], quantity_grams),
    )

    if source_type != CATALOG_PRODUCT_SOURCE_TYPE or micronutrient_panel_per_100g is None:
        return NutrientTotalLine(
            macros=macros, micronutrients=None, micronutrients_status="unavailable"
        )

    micronutrients = {
        field: (_scale(value, quantity_grams) if value is not None else None)
        for field, value in micronutrient_panel_per_100g.items()
    }
    return NutrientTotalLine(
        macros=macros, micronutrients=micronutrients, micronutrients_status="available"
    )


def _merge_micronutrients(
    lines: Iterable[NutrientTotalLine],
) -> dict[str, float | None] | None:
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


def calculate_day_nutrient_total(lines: Iterable[NutrientTotalLine]) -> NutrientTotalLine:
    lines = list(lines)
    if not lines:
        return NutrientTotalLine(
            macros=ZERO_MACROS, micronutrients=None, micronutrients_status="unavailable"
        )

    macros = ZERO_MACROS
    for line in lines:
        macros = macros + line.macros

    statuses = {line.micronutrients_status for line in lines}
    day_status: MicronutrientStatus
    if statuses == {"available"}:
        day_status = "available"
    elif statuses == {"unavailable"}:
        day_status = "unavailable"
    else:
        day_status = "partial"

    micronutrients = _merge_micronutrients(lines) if day_status != "unavailable" else None
    is_estimated = any(line.is_estimated for line in lines)
    return NutrientTotalLine(
        macros=macros,
        micronutrients=micronutrients,
        micronutrients_status=day_status,
        is_estimated=is_estimated,
    )
