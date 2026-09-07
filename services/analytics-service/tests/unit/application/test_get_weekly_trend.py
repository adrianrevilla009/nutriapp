from __future__ import annotations

import uuid
from datetime import date, timedelta

from application.queries.get_weekly_trend import (
    MAX_WINDOW_DAYS,
    GetWeeklyTrendHandler,
    GetWeeklyTrendQuery,
)
from tests.fixtures.factories import FakeDailyLogSummaryRepository

TODAY = date(2026, 6, 8)


async def test_unentitled_user_still_succeeds_not_gated():
    # No entitlement port is even constructible here -- GetWeeklyTrendHandler
    # takes only a DailyLogSummaryRepositoryPort, a structural guard that
    # this query can never be gated.
    import inspect

    signature = inspect.signature(GetWeeklyTrendHandler.__init__)
    assert set(signature.parameters) == {"self", "daily_log_summary"}


async def test_small_n_two_days_reports_explicit_sample_size():
    summary = FakeDailyLogSummaryRepository()
    user_id = uuid.uuid4()
    for entry_id, days_ago in ((uuid.uuid4(), 0), (uuid.uuid4(), 1)):
        await summary.apply_food_entry(
            entry_id, user_id, TODAY - timedelta(days=days_ago), 2000.0, 100.0, 200.0, 60.0
        )
    handler = GetWeeklyTrendHandler(summary)

    result = await handler.handle(GetWeeklyTrendQuery(user_id=user_id, as_of=TODAY, window_days=7))

    assert result.running_total.sample_size == 2
    assert result.running_total.window_days == 7
    assert result.streak.sample_size == 2


async def test_large_n_ninety_days_correct_aggregation():
    summary = FakeDailyLogSummaryRepository()
    user_id = uuid.uuid4()
    for n in range(90):
        await summary.apply_food_entry(
            uuid.uuid4(), user_id, TODAY - timedelta(days=n), 2000.0, 100.0, 200.0, 60.0
        )
    handler = GetWeeklyTrendHandler(summary)

    result = await handler.handle(GetWeeklyTrendQuery(user_id=user_id, as_of=TODAY, window_days=90))

    assert result.running_total.sample_size == 90
    assert result.running_total.avg_calories_kcal == 2000.0
    assert result.streak.current_streak_days == 90


class _RecordingDailyLogSummaryRepository(FakeDailyLogSummaryRepository):
    def __init__(self) -> None:
        super().__init__()
        self.list_window_calls: list[tuple] = []

    async def list_window(self, user_id, start_date, end_date):
        self.list_window_calls.append((start_date, end_date))
        return await super().list_window(user_id, start_date, end_date)


async def test_window_exceeding_max_is_clamped_never_unbounded():
    summary = _RecordingDailyLogSummaryRepository()
    handler = GetWeeklyTrendHandler(summary)

    await handler.handle(
        GetWeeklyTrendQuery(user_id=uuid.uuid4(), as_of=TODAY, window_days=MAX_WINDOW_DAYS + 500)
    )

    (start_date, end_date) = summary.list_window_calls[0]
    assert end_date == TODAY
    assert (end_date - start_date).days + 1 == MAX_WINDOW_DAYS
