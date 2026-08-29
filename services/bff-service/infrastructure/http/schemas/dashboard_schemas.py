"""DashboardResponse and its three section envelope shapes -- purely
structural reshaping of the three downstream payloads
(application/queries/get_dashboard.py's DashboardResult) into the exact
shape the frontend needs (bff-agent.md: "allowed and expected... as long
as it's purely structural"). No field is renamed to a different meaning,
computed, or derived here -- every value is copied straight through from
whatever the owning domain service already computed.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from application.queries.get_dashboard import DashboardResult
from domain.value_objects.section_status import SectionStatus

_SectionStatusLiteral = Literal["available", "unavailable"]
_UnavailableReasonLiteral = Literal["downstream_error", "not_yet_computed"]


class DiarySummarySection(BaseModel):
    total_calories_kcal: float
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    total_water_ml: float
    fasting_windows_ended: int


class DiarySummaryEnvelope(BaseModel):
    status: _SectionStatusLiteral
    reason: _UnavailableReasonLiteral | None = None
    data: DiarySummarySection | None = None


class NutrientTotalsSection(BaseModel):
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    micronutrients: dict[str, float | None] | None
    micronutrients_status: str
    is_estimated: bool


class NutrientTotalsEnvelope(BaseModel):
    status: _SectionStatusLiteral
    reason: _UnavailableReasonLiteral | None = None
    data: NutrientTotalsSection | None = None


class NutritionTargetSection(BaseModel):
    calorie_target_kcal: float
    protein_g_min: float
    protein_g_max: float
    fat_g_min: float
    carbs_g: float
    goal_type: str


class NutritionTargetEnvelope(BaseModel):
    status: _SectionStatusLiteral
    reason: _UnavailableReasonLiteral | None = None
    data: NutritionTargetSection | None = None


class DashboardResponse(BaseModel):
    diary_summary: DiarySummaryEnvelope
    nutrient_totals: NutrientTotalsEnvelope
    target: NutritionTargetEnvelope


def _diary_summary_envelope(status: SectionStatus[Any]) -> DiarySummaryEnvelope:
    data = None
    if status.data is not None:
        data = DiarySummarySection(
            total_calories_kcal=status.data.total_calories_kcal,
            total_protein_g=status.data.total_protein_g,
            total_carbs_g=status.data.total_carbs_g,
            total_fat_g=status.data.total_fat_g,
            total_water_ml=status.data.total_water_ml,
            fasting_windows_ended=status.data.fasting_windows_ended,
        )
    return DiarySummaryEnvelope(status=status.status, reason=status.reason, data=data)


def _nutrient_totals_envelope(status: SectionStatus[Any]) -> NutrientTotalsEnvelope:
    data = None
    if status.data is not None:
        data = NutrientTotalsSection(
            calories_kcal=status.data.calories_kcal,
            protein_g=status.data.protein_g,
            carbs_g=status.data.carbs_g,
            fat_g=status.data.fat_g,
            micronutrients=status.data.micronutrients,
            micronutrients_status=status.data.micronutrients_status,
            is_estimated=status.data.is_estimated,
        )
    return NutrientTotalsEnvelope(status=status.status, reason=status.reason, data=data)


def _nutrition_target_envelope(status: SectionStatus[Any]) -> NutritionTargetEnvelope:
    data = None
    if status.data is not None:
        data = NutritionTargetSection(
            calorie_target_kcal=status.data.calorie_target_kcal,
            protein_g_min=status.data.protein_g_min,
            protein_g_max=status.data.protein_g_max,
            fat_g_min=status.data.fat_g_min,
            carbs_g=status.data.carbs_g,
            goal_type=status.data.goal_type,
        )
    return NutritionTargetEnvelope(status=status.status, reason=status.reason, data=data)


def dashboard_result_to_response(result: DashboardResult) -> DashboardResponse:
    return DashboardResponse(
        diary_summary=_diary_summary_envelope(result.diary_summary),
        nutrient_totals=_nutrient_totals_envelope(result.nutrient_totals),
        target=_nutrition_target_envelope(result.target),
    )
