from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from application.dto.disclaimers import INFORMATIONAL_ESTIMATE_DISCLAIMER
from domain.entities.nutrition_target import NutritionTarget


@dataclass(frozen=True, slots=True)
class NutritionTargetDTO:
    user_id: uuid.UUID
    bmr_kcal: float
    tdee_kcal: float
    calorie_target_kcal: float
    protein_g_min: float
    protein_g_max: float
    fat_g_min: float
    carbs_g: float
    goal_type: str
    activity_level: str
    clamped: bool
    clamp_reason: str | None
    formula_version: str
    effective_from: datetime
    disclaimer: str = field(default=INFORMATIONAL_ESTIMATE_DISCLAIMER)

    @classmethod
    def from_entity(cls, target: NutritionTarget) -> NutritionTargetDTO:
        return cls(
            user_id=target.user_id,
            bmr_kcal=target.bmr_kcal,
            tdee_kcal=target.tdee_kcal,
            calorie_target_kcal=target.calorie_target_kcal,
            protein_g_min=target.macro_targets.protein_g_min,
            protein_g_max=target.macro_targets.protein_g_max,
            fat_g_min=target.macro_targets.fat_g_min,
            carbs_g=target.macro_targets.carbs_g,
            goal_type=target.goal_type.value,
            activity_level=target.activity_level.value,
            clamped=target.clamped,
            clamp_reason=target.clamp_reason,
            formula_version=target.formula_version,
            effective_from=target.effective_from,
        )
