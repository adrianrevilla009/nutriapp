"""Shared JSON (de)serialization helpers for value objects persisted as
JSONB columns -- kept out of the repository classes themselves so the
(de)serialization shape is defined and tested in exactly one place."""

from __future__ import annotations

from typing import Any

from domain.value_objects.nutrient_total_line import MacroAmounts, NutrientTotalLine


def nutrient_total_line_to_dict(line: NutrientTotalLine) -> dict[str, Any]:
    return {
        "macros": {
            "calories_kcal": line.macros.calories_kcal,
            "protein_g": line.macros.protein_g,
            "carbs_g": line.macros.carbs_g,
            "fat_g": line.macros.fat_g,
        },
        "micronutrients": dict(line.micronutrients) if line.micronutrients is not None else None,
        "micronutrients_status": line.micronutrients_status,
        "is_estimated": line.is_estimated,
    }


def nutrient_total_line_from_dict(data: dict[str, Any]) -> NutrientTotalLine:
    macros = data["macros"]
    return NutrientTotalLine(
        macros=MacroAmounts(
            calories_kcal=macros["calories_kcal"],
            protein_g=macros["protein_g"],
            carbs_g=macros["carbs_g"],
            fat_g=macros["fat_g"],
        ),
        micronutrients=data.get("micronutrients"),
        micronutrients_status=data["micronutrients_status"],
        is_estimated=data.get("is_estimated", False),
    )
