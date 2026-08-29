"""Fake ports + default result builders shared by unit tests
(testing-strategy SKILL.md: one factory module per service)."""

from __future__ import annotations

from datetime import date

from domain.ports.diary_summary_port import DiarySummaryResult
from domain.ports.nutrition_target_port import NutritionTargetResult
from domain.ports.nutrition_totals_port import NutritionTotalsResult


def build_diary_summary_result(**overrides: object) -> DiarySummaryResult:
    defaults: dict[str, object] = {
        "total_calories_kcal": 1850.0,
        "total_protein_g": 120.0,
        "total_carbs_g": 180.0,
        "total_fat_g": 60.0,
        "total_water_ml": 1500.0,
        "fasting_windows_ended": 1,
    }
    defaults.update(overrides)
    return DiarySummaryResult(**defaults)  # type: ignore[arg-type]


def build_nutrition_totals_result(**overrides: object) -> NutritionTotalsResult:
    defaults: dict[str, object] = {
        "calories_kcal": 1820.0,
        "protein_g": 118.0,
        "carbs_g": 175.0,
        "fat_g": 58.0,
        "micronutrients": {"vitamin_c_mg": 90.0},
        "micronutrients_status": "available",
        "is_estimated": False,
    }
    defaults.update(overrides)
    return NutritionTotalsResult(**defaults)  # type: ignore[arg-type]


def build_nutrition_target_result(**overrides: object) -> NutritionTargetResult:
    defaults: dict[str, object] = {
        "calorie_target_kcal": 2200.0,
        "protein_g_min": 110.0,
        "protein_g_max": 180.0,
        "fat_g_min": 50.0,
        "carbs_g": 220.0,
        "goal_type": "MAINTAIN",
    }
    defaults.update(overrides)
    return NutritionTargetResult(**defaults)  # type: ignore[arg-type]


DEFAULT_DASHBOARD_DATE = date(2026, 8, 28)


class FakeDiarySummaryPort:
    def __init__(self, result: DiarySummaryResult | None = None, error: Exception | None = None):
        self._result = result if result is not None else build_diary_summary_result()
        self._error = error
        self.calls: list[tuple[date, str]] = []

    async def get_summary(
        self, summary_date: date, authorization_header: str
    ) -> DiarySummaryResult:
        self.calls.append((summary_date, authorization_header))
        if self._error is not None:
            raise self._error
        return self._result


class FakeNutritionTotalsPort:
    def __init__(self, result: NutritionTotalsResult | None = None, error: Exception | None = None):
        self._result = result if result is not None else build_nutrition_totals_result()
        self._error = error
        self.calls: list[tuple[date, str]] = []

    async def get_totals(
        self, total_date: date, authorization_header: str
    ) -> NutritionTotalsResult:
        self.calls.append((total_date, authorization_header))
        if self._error is not None:
            raise self._error
        return self._result


class FakeNutritionTargetPort:
    def __init__(
        self,
        result: object = None,
        error: Exception | None = None,
    ):
        """`result` is either a NutritionTargetResult, a
        NutritionTargetNotComputedYet instance, or None (defaults to a
        built NutritionTargetResult)."""
        self._result = result if result is not None else build_nutrition_target_result()
        self._error = error
        self.calls: list[str] = []

    async def get_target(self, authorization_header: str) -> object:
        self.calls.append(authorization_header)
        if self._error is not None:
            raise self._error
        return self._result
