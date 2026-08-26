from __future__ import annotations

import pytest

from domain.services.tdee_calculator import (
    ACTIVITY_FACTORS,
    UnrecognizedActivityLevelError,
    calculate_tdee,
)
from domain.value_objects.activity_level import ActivityLevel

FIXED_BMR_KCAL = 1673.75


@pytest.mark.parametrize("activity_level", list(ActivityLevel))
def test_each_activity_level_applies_exact_published_factor(activity_level):
    result = calculate_tdee(bmr_kcal=FIXED_BMR_KCAL, activity_level=activity_level)
    assert result == pytest.approx(FIXED_BMR_KCAL * ACTIVITY_FACTORS[activity_level])


def test_published_factor_values_match_addendum_1():
    assert ACTIVITY_FACTORS[ActivityLevel.SEDENTARY] == 1.2
    assert ACTIVITY_FACTORS[ActivityLevel.LIGHT] == 1.375
    assert ACTIVITY_FACTORS[ActivityLevel.MODERATE] == 1.55
    assert ACTIVITY_FACTORS[ActivityLevel.ACTIVE] == 1.725
    assert ACTIVITY_FACTORS[ActivityLevel.VERY_ACTIVE] == 1.9


def test_unrecognized_activity_level_raises():
    with pytest.raises(UnrecognizedActivityLevelError):
        calculate_tdee(bmr_kcal=FIXED_BMR_KCAL, activity_level="NOT_A_LEVEL")  # type: ignore[arg-type]


def test_activity_adjustment_kcal_is_always_ignored():
    with_none = calculate_tdee(
        bmr_kcal=FIXED_BMR_KCAL,
        activity_level=ActivityLevel.MODERATE,
        activity_adjustment_kcal=None,
    )
    with_value = calculate_tdee(
        bmr_kcal=FIXED_BMR_KCAL,
        activity_level=ActivityLevel.MODERATE,
        activity_adjustment_kcal=500.0,
    )
    assert with_none == with_value == pytest.approx(FIXED_BMR_KCAL * 1.55)
