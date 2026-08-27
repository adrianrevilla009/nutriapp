"""Macro repartition calculator -- applies protein/fat/carb splits to a
calorie target (domain-calculation-conventions SKILL.md section 2):
  - Protein: 1.6-2.2 g/kg body weight (a range, not a point value).
  - Fat: minimum 20% of total calories.
  - Carbs: the remainder after protein (at the midpoint of its range) and
    fat (at its floor) are fixed -- floored at 0g rather than going
    negative for a pathological low-calorie-target input, surfaced via
    `carbs_floored` rather than silently returned as a negative number.
"""

from __future__ import annotations

from domain.value_objects.macro_target_range import MacroTargetRange

PROTEIN_G_PER_KG_MIN = 1.6
PROTEIN_G_PER_KG_MAX = 2.2
FAT_MIN_CALORIE_FRACTION = 0.20
KCAL_PER_GRAM_PROTEIN = 4.0
KCAL_PER_GRAM_FAT = 9.0
KCAL_PER_GRAM_CARB = 4.0


def calculate_macro_repartition(
    *, calorie_target_kcal: float, weight_kg: float
) -> MacroTargetRange:
    if weight_kg <= 0:
        raise ValueError("weight_kg must be positive.")
    if calorie_target_kcal < 0:
        raise ValueError("calorie_target_kcal must not be negative.")

    protein_g_min = PROTEIN_G_PER_KG_MIN * weight_kg
    protein_g_max = PROTEIN_G_PER_KG_MAX * weight_kg
    protein_g_midpoint = (protein_g_min + protein_g_max) / 2.0

    fat_g_min = (calorie_target_kcal * FAT_MIN_CALORIE_FRACTION) / KCAL_PER_GRAM_FAT

    protein_kcal_at_midpoint = protein_g_midpoint * KCAL_PER_GRAM_PROTEIN
    fat_kcal_at_floor = fat_g_min * KCAL_PER_GRAM_FAT
    remaining_kcal = calorie_target_kcal - protein_kcal_at_midpoint - fat_kcal_at_floor

    carbs_floored = remaining_kcal < 0
    carbs_g = max(remaining_kcal, 0.0) / KCAL_PER_GRAM_CARB

    return MacroTargetRange(
        protein_g_min=protein_g_min,
        protein_g_max=protein_g_max,
        fat_g_min=fat_g_min,
        carbs_g=carbs_g,
        carbs_floored=carbs_floored,
    )
