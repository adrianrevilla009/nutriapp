"""GetWeeklyTrendHandler -- backs `GET /api/v1/analytics/trends/weekly`.
**Not Pro-gated** (implementation plan section 1 acceptance criterion 2):
holds no reference to any entitlement port at all, a structural guard
mirroring `ListFollowingHandler`/`ListFollowersHandler`'s identical
not-gated pattern in `social-service`.

Enforces CLAUDE.md's pagination rule by construction: the requested
window is clamped to `MAX_WINDOW_DAYS` before ever calling the
repository, so the repository is never asked for an unbounded range."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from domain.ports.daily_log_summary_repository_port import DailyLogSummaryRepositoryPort
from domain.services.trend_calculator import compute_running_totals, compute_streak
from domain.value_objects.macro_running_total import MacroRunningTotal
from domain.value_objects.streak_summary import StreakSummary

MAX_WINDOW_DAYS = 90
DEFAULT_WINDOW_DAYS = 7


@dataclass(frozen=True, slots=True)
class GetWeeklyTrendQuery:
    user_id: uuid.UUID
    as_of: date
    window_days: int = DEFAULT_WINDOW_DAYS


@dataclass(frozen=True, slots=True)
class WeeklyTrendResult:
    streak: StreakSummary
    running_total: MacroRunningTotal


class GetWeeklyTrendHandler:
    def __init__(self, daily_log_summary: DailyLogSummaryRepositoryPort) -> None:
        self._daily_log_summary = daily_log_summary

    async def handle(self, query: GetWeeklyTrendQuery) -> WeeklyTrendResult:
        window_days = min(query.window_days, MAX_WINDOW_DAYS)
        start_date = query.as_of - timedelta(days=window_days - 1)

        daily_rows = await self._daily_log_summary.list_window(
            query.user_id, start_date, query.as_of
        )
        logged_dates = [row.on_date for row in daily_rows]

        streak = compute_streak(logged_dates, window_days, query.as_of)
        running_total = compute_running_totals(daily_rows, window_days)
        return WeeklyTrendResult(streak=streak, running_total=running_total)
