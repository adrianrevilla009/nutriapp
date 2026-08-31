from __future__ import annotations

from domain.value_objects.nutrient_totals import ZERO_MACROS, MacroAmounts, NutrientTotals


def test_macro_amounts_add():
    a = MacroAmounts(calories_kcal=100, protein_g=10, carbs_g=20, fat_g=5)
    b = MacroAmounts(calories_kcal=50, protein_g=5, carbs_g=10, fat_g=2)
    total = a + b
    assert total == MacroAmounts(calories_kcal=150, protein_g=15, carbs_g=30, fat_g=7)


def test_zero_macros_is_additive_identity():
    a = MacroAmounts(calories_kcal=100, protein_g=10, carbs_g=20, fat_g=5)
    assert (a + ZERO_MACROS) == a


def test_nutrient_totals_partial_status_is_a_distinct_literal_value():
    partial = NutrientTotals(
        macros=ZERO_MACROS,
        macros_status="available",
        micronutrients={"sugars_g": 1.0},
        micronutrients_status="partial",
    )
    assert partial.micronutrients_status == "partial"
    assert partial.micronutrients_status not in ("available", "unavailable")


def test_nutrient_totals_macros_status_partial_is_a_distinct_literal_value():
    partial = NutrientTotals(
        macros=ZERO_MACROS,
        macros_status="partial",
        micronutrients=None,
        micronutrients_status="unavailable",
    )
    assert partial.macros_status == "partial"
    assert partial.macros_status not in ("available", "unavailable")
