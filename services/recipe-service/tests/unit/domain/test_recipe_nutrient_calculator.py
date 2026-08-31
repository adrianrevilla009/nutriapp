"""recipe_nutrient_calculator.py against
packages/shared-contracts/fixtures/nutrient_calculation_reference_cases.json
-- hand-computed reference recipes with known expected totals (test-plan
section 1, domain-calculation-conventions SKILL.md)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from domain.services.recipe_nutrient_calculator import (
    calculate_ingredient_nutrient_total,
    calculate_recipe_nutrient_totals,
)
from domain.value_objects.nutrient_panel import NutrientPanel
from domain.value_objects.nutrient_totals import MacroAmounts, NutrientTotals

FIXTURE_PATH = (
    Path(__file__).parents[5]
    / "packages"
    / "shared-contracts"
    / "fixtures"
    / "nutrient_calculation_reference_cases.json"
)


def _load_cases() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text())["cases"]


CASES = _load_cases()


def _panel_from_dict(raw: dict | None) -> NutrientPanel | None:
    return None if raw is None else NutrientPanel(**raw)


def _expected_totals(raw: dict) -> NutrientTotals:
    return NutrientTotals(
        macros=MacroAmounts(**raw["macros"]),
        macros_status=raw["macros_status"],
        micronutrients=raw["micronutrients"],
        micronutrients_status=raw["micronutrients_status"],
    )


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_reference_case_per_recipe_and_per_serving_totals_match(case: dict):
    ingredient_lines = [
        calculate_ingredient_nutrient_total(
            quantity_grams=ingredient["quantity_grams"],
            nutrition_per_100g=_panel_from_dict(ingredient["nutrition_per_100g"]),
        )
        for ingredient in case["ingredients"]
    ]

    result = calculate_recipe_nutrient_totals(ingredient_lines, servings=case["servings"])

    assert result.per_recipe == _expected_totals(case["expected_per_recipe"])
    assert result.per_serving == _expected_totals(case["expected_per_serving"])


def test_zero_ingredients_never_raises_a_division_error():
    result = calculate_recipe_nutrient_totals([], servings=5)
    assert result.per_recipe.macros == MacroAmounts(0.0, 0.0, 0.0, 0.0)
    assert result.per_serving.macros == MacroAmounts(0.0, 0.0, 0.0, 0.0)
    assert result.per_recipe.micronutrients_status == "unavailable"
    assert result.per_recipe.macros_status == "unavailable"
    assert result.per_serving.macros_status == "unavailable"


def test_a_missing_individual_macro_field_scales_to_zero_not_an_error():
    """A present nutrition panel with one macro field itself null (e.g.
    `energy_kcal` unknown for this specific product) must not raise or
    propagate `None` into the summed total -- it contributes 0.0 for that
    one field only, the other three macro fields still compute normally."""
    panel = NutrientPanel(energy_kcal=None, protein_g=10, carbohydrates_g=20, fat_g=5)
    line = calculate_ingredient_nutrient_total(quantity_grams=100, nutrition_per_100g=panel)
    assert line.macros.calories_kcal == 0.0
    assert line.macros.protein_g == 10.0
    assert line.micronutrients_status == "available"
    assert line.macros_status == "available"


def test_ingredient_with_no_panel_contributes_zero_and_is_unavailable():
    line = calculate_ingredient_nutrient_total(quantity_grams=100, nutrition_per_100g=None)
    assert line.macros == MacroAmounts(0.0, 0.0, 0.0, 0.0)
    assert line.micronutrients is None
    assert line.micronutrients_status == "unavailable"
    assert line.macros_status == "unavailable"


def test_mixed_ingredients_recipe_status_is_partial_not_available_or_unavailable():
    available = calculate_ingredient_nutrient_total(
        quantity_grams=100,
        nutrition_per_100g=NutrientPanel(energy_kcal=100, protein_g=5, carbohydrates_g=10, fat_g=2),
    )
    unavailable = calculate_ingredient_nutrient_total(quantity_grams=50, nutrition_per_100g=None)

    result = calculate_recipe_nutrient_totals([available, unavailable], servings=1)

    assert result.per_recipe.micronutrients_status == "partial"
    assert result.per_recipe.macros_status == "partial"
    assert result.per_serving.macros_status == "partial"


def test_all_unavailable_ingredients_recipe_status_is_unavailable():
    lines = [
        calculate_ingredient_nutrient_total(quantity_grams=100, nutrition_per_100g=None),
        calculate_ingredient_nutrient_total(quantity_grams=50, nutrition_per_100g=None),
    ]
    result = calculate_recipe_nutrient_totals(lines, servings=2)
    assert result.per_recipe.micronutrients_status == "unavailable"
    assert result.per_recipe.micronutrients is None
    assert result.per_recipe.macros_status == "unavailable"
    assert result.per_serving.macros_status == "unavailable"


def test_all_available_ingredients_recipe_macros_status_is_available():
    lines = [
        calculate_ingredient_nutrient_total(
            quantity_grams=100,
            nutrition_per_100g=NutrientPanel(
                energy_kcal=100, protein_g=5, carbohydrates_g=10, fat_g=2
            ),
        ),
        calculate_ingredient_nutrient_total(
            quantity_grams=50,
            nutrition_per_100g=NutrientPanel(
                energy_kcal=50, protein_g=2, carbohydrates_g=5, fat_g=1
            ),
        ),
    ]
    result = calculate_recipe_nutrient_totals(lines, servings=2)
    assert result.per_recipe.macros_status == "available"
    assert result.per_serving.macros_status == "available"
