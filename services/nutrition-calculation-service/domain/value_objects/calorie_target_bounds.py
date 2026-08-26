"""CalorieTargetBounds -- the safety bounds a calculated calorie target is
clamped to (implementation plan Addendum 1 section 9.3, confirmed as
proposed):
  - floor: never below BMR.
  - deficit cap: a LOSE goal is never more than `deficit_cap_kcal_per_day`
    below TDEE.
  - surplus cap: a GAIN goal is never more than `surplus_cap_kcal_per_day`
    above TDEE.

Source: internal decision (no single published clinical guideline
mandates one number; 1000 kcal/day deficit and 500 kcal/day surplus are
the commonly-cited "generally recognized as safe" outer bounds used by
most consumer nutrition calculators for a roughly 1-2 lb/week rate of
change) -- see calorie_target_calculator.py's docstring for how these are
applied, and domain-calculation-conventions SKILL.md for why any future
change to these numbers requires an ADR, not a silent tweak.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_DEFICIT_CAP_KCAL_PER_DAY = 1000.0
DEFAULT_SURPLUS_CAP_KCAL_PER_DAY = 500.0


@dataclass(frozen=True, slots=True)
class CalorieTargetBounds:
    deficit_cap_kcal_per_day: float = DEFAULT_DEFICIT_CAP_KCAL_PER_DAY
    surplus_cap_kcal_per_day: float = DEFAULT_SURPLUS_CAP_KCAL_PER_DAY


DEFAULT_CALORIE_TARGET_BOUNDS = CalorieTargetBounds()
