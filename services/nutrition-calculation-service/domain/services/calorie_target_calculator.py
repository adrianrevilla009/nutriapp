"""Calorie target calculator -- TDEE +/- goal_adjustment, clamped to the
safety bounds in domain/value_objects/calorie_target_bounds.py
(implementation plan Addendum 1 section 9.3, confirmed as proposed):
  - floor: never below BMR.
  - deficit cap: a LOSE goal is never more than `deficit_cap_kcal_per_day`
    below TDEE.
  - surplus cap: a GAIN goal is never more than `surplus_cap_kcal_per_day`
    above TDEE.

A clamp is always surfaced (`clamped=True`, `clamp_reason`) rather than
silently honored -- domain-calculation-conventions SKILL.md's "no false
precision" / transparency rule. When both a goal-specific cap and the BMR
floor would independently bind, the floor wins and `clamp_reason` names
the floor specifically (the tighter, safety-critical constraint) rather
than the goal-specific cap that would otherwise also apply -- the caller
needs to know which rule actually determined the final number.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.calorie_target_bounds import (
    DEFAULT_CALORIE_TARGET_BOUNDS,
    CalorieTargetBounds,
)
from domain.value_objects.goal_type import GoalType


@dataclass(frozen=True, slots=True)
class CalorieTargetResult:
    calorie_target_kcal: float
    clamped: bool
    clamp_reason: str | None


def calculate_calorie_target(
    *,
    bmr_kcal: float,
    tdee_kcal: float,
    goal_type: GoalType,
    goal_adjustment_kcal: float = 0.0,
    bounds: CalorieTargetBounds = DEFAULT_CALORIE_TARGET_BOUNDS,
) -> CalorieTargetResult:
    if goal_type is GoalType.MAINTAIN:
        target = tdee_kcal
    elif goal_type is GoalType.LOSE:
        target = tdee_kcal - abs(goal_adjustment_kcal)
    elif goal_type is GoalType.GAIN:
        target = tdee_kcal + abs(goal_adjustment_kcal)
    else:
        raise ValueError(f"Unrecognized goal_type: {goal_type!r}")

    clamped = False
    clamp_reason: str | None = None

    if goal_type is GoalType.LOSE:
        deficit_floor = tdee_kcal - bounds.deficit_cap_kcal_per_day
        if target < deficit_floor:
            target = deficit_floor
            clamped = True
            clamp_reason = (
                f"Deficit capped at {bounds.deficit_cap_kcal_per_day:.0f} kcal/day below TDEE."
            )
    elif goal_type is GoalType.GAIN:
        surplus_ceiling = tdee_kcal + bounds.surplus_cap_kcal_per_day
        if target > surplus_ceiling:
            target = surplus_ceiling
            clamped = True
            clamp_reason = (
                f"Surplus capped at {bounds.surplus_cap_kcal_per_day:.0f} kcal/day above TDEE."
            )

    if target < bmr_kcal:
        target = bmr_kcal
        clamped = True
        clamp_reason = (
            "Target floored at BMR -- a calorie target is never set below resting energy needs."
        )

    return CalorieTargetResult(
        calorie_target_kcal=target, clamped=clamped, clamp_reason=clamp_reason
    )
