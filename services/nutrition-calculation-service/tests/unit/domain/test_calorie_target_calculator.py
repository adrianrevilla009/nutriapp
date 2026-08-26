from __future__ import annotations

import pytest

from domain.services.calorie_target_calculator import calculate_calorie_target
from domain.value_objects.goal_type import GoalType

BMR = 1000.0
TDEE = 2300.0


def test_lose_goal_within_deficit_cap_not_clamped():
    result = calculate_calorie_target(
        bmr_kcal=BMR, tdee_kcal=TDEE, goal_type=GoalType.LOSE, goal_adjustment_kcal=400.0
    )
    assert result.calorie_target_kcal == pytest.approx(TDEE - 400.0)
    assert result.clamped is False
    assert result.clamp_reason is None


def test_lose_goal_beyond_deficit_cap_clamped_to_tdee_minus_1000():
    result = calculate_calorie_target(
        bmr_kcal=BMR, tdee_kcal=TDEE, goal_type=GoalType.LOSE, goal_adjustment_kcal=1500.0
    )
    assert result.calorie_target_kcal == pytest.approx(TDEE - 1000.0)
    assert result.clamped is True
    assert "1000" in result.clamp_reason
    assert "deficit" in result.clamp_reason.lower()


def test_gain_goal_beyond_surplus_cap_clamped_to_tdee_plus_500():
    result = calculate_calorie_target(
        bmr_kcal=BMR, tdee_kcal=TDEE, goal_type=GoalType.GAIN, goal_adjustment_kcal=900.0
    )
    assert result.calorie_target_kcal == pytest.approx(TDEE + 500.0)
    assert result.clamped is True
    assert "500" in result.clamp_reason
    assert "surplus" in result.clamp_reason.lower()


def test_clamp_that_would_still_fall_below_bmr_floors_at_bmr_with_distinct_reason():
    # TDEE close to BMR: even the deficit-capped value (TDEE - 1000) is below BMR.
    low_tdee = 1600.0
    result = calculate_calorie_target(
        bmr_kcal=BMR, tdee_kcal=low_tdee, goal_type=GoalType.LOSE, goal_adjustment_kcal=2000.0
    )
    assert result.calorie_target_kcal == pytest.approx(BMR)
    assert result.clamped is True
    assert "BMR" in result.clamp_reason
    assert "deficit" not in result.clamp_reason.lower()


def test_maintain_goal_targets_tdee_exactly():
    result = calculate_calorie_target(bmr_kcal=BMR, tdee_kcal=TDEE, goal_type=GoalType.MAINTAIN)
    assert result.calorie_target_kcal == pytest.approx(TDEE)
    assert result.clamped is False
    assert result.clamp_reason is None
