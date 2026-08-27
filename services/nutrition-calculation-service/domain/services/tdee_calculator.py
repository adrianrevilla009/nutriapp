"""TDEE calculator -- BMR x activity factor (Physical Activity Level).

PAL table confirmed in implementation plan Addendum 1 section 9.2 (standard
published activity-multiplier values used across most clinical and
consumer nutrition calculators building on the Mifflin-St Jeor baseline):
  SEDENTARY   = 1.2   (little or no exercise)
  LIGHT       = 1.375 (light exercise 1-3 days/week)
  MODERATE    = 1.55  (moderate exercise 3-5 days/week)
  ACTIVE      = 1.725 (hard exercise 6-7 days/week)
  VERY_ACTIVE = 1.9   (very hard exercise / physical job)

`activity_adjustment_kcal` is a reserved seam for activity-service's
exercise-derived TDEE adjustment (implementation plan section 1, item 2 /
section 9.7) -- always ignored this pass; TDEE is computed from the
activity-factor table alone regardless of what is passed here.
"""

from __future__ import annotations

from domain.value_objects.activity_level import ActivityLevel

ACTIVITY_FACTORS: dict[ActivityLevel, float] = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.LIGHT: 1.375,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.ACTIVE: 1.725,
    ActivityLevel.VERY_ACTIVE: 1.9,
}


class UnrecognizedActivityLevelError(ValueError):
    """Raised for an activity level absent from ACTIVITY_FACTORS."""


def calculate_tdee(
    *,
    bmr_kcal: float,
    activity_level: ActivityLevel,
    activity_adjustment_kcal: float | None = None,
) -> float:
    del activity_adjustment_kcal  # reserved seam, always ignored this pass -- see module docstring
    try:
        factor = ACTIVITY_FACTORS[activity_level]
    except KeyError as exc:
        raise UnrecognizedActivityLevelError(
            f"Unrecognized activity level: {activity_level!r}"
        ) from exc
    return bmr_kcal * factor
