"""NutritionTotalsPort -- calls nutrition-calculation-service's existing
public `GET /api/v1/nutrition/totals/{date}` endpoint (already-merged, no
change needed there). The incoming request's `Authorization` header is
forwarded unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True, slots=True)
class NutritionTotalsResult:
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    micronutrients: dict[str, float | None] | None
    micronutrients_status: str
    is_estimated: bool


class NutritionTotalsUnavailableError(Exception):
    """Raised when nutrition-calculation-service's totals endpoint cannot
    be reached (circuit open, retries exhausted, timeout) or returns a
    non-success response. The caller (GetDashboardHandler) must degrade
    only the `nutrient_totals` section of the response."""


class NutritionTotalsPort(Protocol):
    async def get_totals(
        self, total_date: date, authorization_header: str
    ) -> NutritionTotalsResult: ...
