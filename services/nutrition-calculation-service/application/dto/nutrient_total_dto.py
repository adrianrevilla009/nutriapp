from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

from application.dto.disclaimers import INFORMATIONAL_ESTIMATE_DISCLAIMER
from domain.entities.daily_nutrition_total import DailyNutritionTotal
from domain.value_objects.nutrient_total_line import NutrientTotalLine


@dataclass(frozen=True, slots=True)
class NutrientTotalDTO:
    user_id: uuid.UUID
    total_date: date
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    micronutrients: Mapping[str, float | None] | None
    micronutrients_status: str
    is_estimated: bool
    disclaimer: str = field(default=INFORMATIONAL_ESTIMATE_DISCLAIMER)

    @classmethod
    def from_entity(cls, total: DailyNutritionTotal) -> NutrientTotalDTO:
        return cls.from_line(
            user_id=total.user_id, total_date=total.total_date, line=total.compute_total()
        )

    @classmethod
    def from_line(
        cls, *, user_id: uuid.UUID, total_date: date, line: NutrientTotalLine
    ) -> NutrientTotalDTO:
        return cls(
            user_id=user_id,
            total_date=total_date,
            calories_kcal=line.macros.calories_kcal,
            protein_g=line.macros.protein_g,
            carbs_g=line.macros.carbs_g,
            fat_g=line.macros.fat_g,
            micronutrients=line.micronutrients,
            micronutrients_status=line.micronutrients_status,
            is_estimated=line.is_estimated,
        )
