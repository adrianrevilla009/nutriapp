"""MacroTargetRange -- the macronutrient repartition applied to a calorie
target (domain-calculation-conventions SKILL.md):
  - protein: a range (1.6-2.2 g/kg body weight), never a single point value.
  - fat: a floor (>= 20% of total calories).
  - carbs: the remainder, floored at 0g rather than negative.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MacroTargetRange:
    protein_g_min: float
    protein_g_max: float
    fat_g_min: float
    carbs_g: float
    carbs_floored: bool
