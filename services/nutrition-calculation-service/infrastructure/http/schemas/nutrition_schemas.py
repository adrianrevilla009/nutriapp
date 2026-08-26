"""Pydantic v2 response models for /api/v1/nutrition (api-conventions
SKILL.md). Every response carries `disclaimer` (CLAUDE.md section 8: an
informational estimate, never medical nutrition therapy)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from application.dto.nutrient_total_dto import NutrientTotalDTO
from application.dto.nutrition_target_dto import NutritionTargetDTO


class ErrorResponse(BaseModel):
    error: str
    code: str


class NutritionTargetResponse(BaseModel):
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
    disclaimer: str


def target_dto_to_response(dto: NutritionTargetDTO) -> NutritionTargetResponse:
    # `from_attributes=True`: reads via getattr, so this works regardless of
    # NutritionTargetDTO being a slotted dataclass (no __dict__).
    return NutritionTargetResponse.model_validate(dto, from_attributes=True)


class NutritionTargetHistoryResponse(BaseModel):
    history: list[NutritionTargetResponse]


class NutrientTotalResponse(BaseModel):
    user_id: uuid.UUID
    total_date: date
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    micronutrients: dict[str, float | None] | None
    micronutrients_status: str
    is_estimated: bool
    disclaimer: str


def total_dto_to_response(dto: NutrientTotalDTO) -> NutrientTotalResponse:
    return NutrientTotalResponse.model_validate(dto, from_attributes=True)
