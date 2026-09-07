"""Pydantic v2 response schemas for `/api/v1/analytics/*`. Every trend/
report response carries `sample_size`/`window_days` explicitly (CLAUDE.md's
disclosure rule) -- never a bare number."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from application.queries.get_weekly_trend import WeeklyTrendResult


class StreakSummaryResponse(BaseModel):
    current_streak_days: int
    sample_size: int
    window_days: int


class MacroRunningTotalResponse(BaseModel):
    sample_size: int
    window_days: int
    avg_calories_kcal: float | None
    avg_protein_g: float | None
    avg_carbs_g: float | None
    avg_fat_g: float | None
    avg_water_ml: float | None
    target_calories_kcal: float | None


class WeeklyTrendResponse(BaseModel):
    streak: StreakSummaryResponse
    running_total: MacroRunningTotalResponse


def weekly_trend_to_response(result: WeeklyTrendResult) -> WeeklyTrendResponse:
    return WeeklyTrendResponse(
        streak=StreakSummaryResponse(
            current_streak_days=result.streak.current_streak_days,
            sample_size=result.streak.sample_size,
            window_days=result.streak.window_days,
        ),
        running_total=MacroRunningTotalResponse(
            sample_size=result.running_total.sample_size,
            window_days=result.running_total.window_days,
            avg_calories_kcal=result.running_total.avg_calories_kcal,
            avg_protein_g=result.running_total.avg_protein_g,
            avg_carbs_g=result.running_total.avg_carbs_g,
            avg_fat_g=result.running_total.avg_fat_g,
            avg_water_ml=result.running_total.avg_water_ml,
            target_calories_kcal=result.running_total.target_calories_kcal,
        ),
    )


class ReportRequest(BaseModel):
    start_date: date
    end_date: date
