from __future__ import annotations

import pytest

from domain.services.macro_repartition_calculator import calculate_macro_repartition

WEIGHT_KG = 70.0


def test_protein_range_scales_with_body_weight():
    result = calculate_macro_repartition(calorie_target_kcal=2200.0, weight_kg=WEIGHT_KG)
    assert result.protein_g_min == pytest.approx(1.6 * WEIGHT_KG)
    assert result.protein_g_max == pytest.approx(2.2 * WEIGHT_KG)


def test_fat_floor_is_exactly_20_percent_of_calorie_target():
    calorie_target = 2200.0
    result = calculate_macro_repartition(calorie_target_kcal=calorie_target, weight_kg=WEIGHT_KG)
    assert result.fat_g_min * 9.0 == pytest.approx(calorie_target * 0.20)


def test_carbs_is_remainder_after_protein_midpoint_and_fat_floor():
    calorie_target = 2200.0
    result = calculate_macro_repartition(calorie_target_kcal=calorie_target, weight_kg=WEIGHT_KG)
    protein_midpoint = (result.protein_g_min + result.protein_g_max) / 2.0
    expected_carbs_kcal = calorie_target - (protein_midpoint * 4.0) - (result.fat_g_min * 9.0)
    assert result.carbs_g == pytest.approx(expected_carbs_kcal / 4.0)
    assert result.carbs_floored is False


def test_pathological_low_calorie_target_floors_carbs_at_zero_and_flags_it():
    # Protein midpoint alone at 70kg (1.9g/kg) * 4 kcal/g = 532 kcal, fat floor
    # at 20% of 500 kcal = 100 kcal -- together already exceed a 500 kcal target.
    result = calculate_macro_repartition(calorie_target_kcal=500.0, weight_kg=WEIGHT_KG)
    assert result.carbs_g == 0.0
    assert result.carbs_floored is True


def test_non_positive_weight_raises():
    with pytest.raises(ValueError):
        calculate_macro_repartition(calorie_target_kcal=2000.0, weight_kg=0)


def test_negative_calorie_target_raises():
    with pytest.raises(ValueError):
        calculate_macro_repartition(calorie_target_kcal=-1.0, weight_kg=WEIGHT_KG)
