from __future__ import annotations

from domain.services.nutrient_total_calculator import (
    calculate_day_nutrient_total,
    calculate_entry_nutrient_total,
)

MACROS_PER_UNIT = {"calories_kcal": 200.0, "protein_g": 10.0, "carbs_g": 20.0, "fat_g": 5.0}
MICRO_PANEL = {"sugars_g": 8.0, "fiber_g": 2.0, "sodium_mg": 100.0}


def test_single_catalog_entry_full_macro_and_micro_available():
    line = calculate_entry_nutrient_total(
        quantity_grams=150.0,
        macros_per_unit=MACROS_PER_UNIT,
        source_type="catalog_product",
        micronutrient_panel_per_100g=MICRO_PANEL,
    )
    assert line.macros.calories_kcal == 300.0
    assert line.macros.protein_g == 15.0
    assert line.macros.carbs_g == 30.0
    assert line.macros.fat_g == 7.5
    assert line.micronutrients_status == "available"
    assert line.micronutrients["sugars_g"] == 12.0
    assert line.micronutrients["fiber_g"] == 3.0
    assert line.micronutrients["sodium_mg"] == 150.0


def test_catalog_source_without_mirror_match_yet_is_unavailable_never_estimated():
    line = calculate_entry_nutrient_total(
        quantity_grams=100.0,
        macros_per_unit=MACROS_PER_UNIT,
        source_type="catalog_product",
        micronutrient_panel_per_100g=None,
    )
    assert line.macros.calories_kcal == 200.0
    assert line.micronutrients is None
    assert line.micronutrients_status == "unavailable"


def test_non_catalog_source_never_attempts_mirror_lookup():
    for source_type in ("recipe", "ai_detected"):
        line = calculate_entry_nutrient_total(
            quantity_grams=100.0,
            macros_per_unit=MACROS_PER_UNIT,
            source_type=source_type,
            micronutrient_panel_per_100g=MICRO_PANEL,  # even if provided, ignored
        )
        assert line.macros.calories_kcal == 200.0
        assert line.micronutrients is None
        assert line.micronutrients_status == "unavailable"


def test_day_total_sums_entries_and_reflects_partial_status():
    available_line = calculate_entry_nutrient_total(
        quantity_grams=100.0,
        macros_per_unit=MACROS_PER_UNIT,
        source_type="catalog_product",
        micronutrient_panel_per_100g=MICRO_PANEL,
    )
    unavailable_line = calculate_entry_nutrient_total(
        quantity_grams=50.0,
        macros_per_unit=MACROS_PER_UNIT,
        source_type="catalog_product",
        micronutrient_panel_per_100g=None,
    )
    another_unavailable_line = calculate_entry_nutrient_total(
        quantity_grams=75.0,
        macros_per_unit=MACROS_PER_UNIT,
        source_type="ai_detected",
        micronutrient_panel_per_100g=None,
    )

    day_total = calculate_day_nutrient_total(
        [available_line, unavailable_line, another_unavailable_line]
    )

    expected_calories = 200.0 + 100.0 + 150.0
    assert day_total.macros.calories_kcal == expected_calories
    assert day_total.micronutrients_status == "partial"
    assert day_total.micronutrients is not None


def test_day_total_all_available_is_available():
    line = calculate_entry_nutrient_total(
        quantity_grams=100.0,
        macros_per_unit=MACROS_PER_UNIT,
        source_type="catalog_product",
        micronutrient_panel_per_100g=MICRO_PANEL,
    )
    day_total = calculate_day_nutrient_total([line, line])
    assert day_total.micronutrients_status == "available"


def test_day_total_all_unavailable_is_unavailable():
    line = calculate_entry_nutrient_total(
        quantity_grams=100.0,
        macros_per_unit=MACROS_PER_UNIT,
        source_type="ai_detected",
        micronutrient_panel_per_100g=None,
    )
    day_total = calculate_day_nutrient_total([line, line])
    assert day_total.micronutrients_status == "unavailable"
    assert day_total.micronutrients is None


def test_empty_day_total_is_zero_and_unavailable():
    day_total = calculate_day_nutrient_total([])
    assert day_total.macros.calories_kcal == 0.0
    assert day_total.micronutrients_status == "unavailable"
