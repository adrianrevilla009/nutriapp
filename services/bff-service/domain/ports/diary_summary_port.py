"""DiarySummaryPort -- calls diary-service's existing public
`GET /api/v1/diary/summary?date={date}` endpoint (already-merged, no
change needed there). The incoming request's `Authorization` header is
forwarded unchanged (implementation plan section 1 acceptance criterion
1) -- this port never re-derives or re-signs anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True, slots=True)
class DiarySummaryResult:
    total_calories_kcal: float
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    total_water_ml: float
    fasting_windows_ended: int


class DiarySummaryUnavailableError(Exception):
    """Raised when diary-service's summary endpoint cannot be reached
    (circuit open, retries exhausted, timeout) or returns a non-success
    response. The caller (GetDashboardHandler) must degrade only the
    `diary_summary` section of the response -- never fail the whole
    dashboard call."""


class DiarySummaryPort(Protocol):
    async def get_summary(
        self, summary_date: date, authorization_header: str
    ) -> DiarySummaryResult: ...
