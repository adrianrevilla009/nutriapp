from __future__ import annotations

import uuid
from datetime import date

from application.queries.get_daily_summary import GetDailySummaryHandler, GetDailySummaryQuery
from tests.fixtures.factories import FakeDailySummaryCachePort, FakeDailySummaryReadPort

SUMMARY_DATE = date(2026, 8, 26)


def _row() -> dict:
    return dict(
        total_calories_kcal=500.0,
        total_protein_g=30.0,
        total_carbs_g=60.0,
        total_fat_g=10.0,
        total_water_ml=1000.0,
        fasting_windows_ended=1,
    )


async def test_cache_hit_returns_cached_value_without_touching_read_port():
    user_id = uuid.uuid4()
    cache = FakeDailySummaryCachePort()
    cache.cache[(user_id, SUMMARY_DATE)] = _row()
    read_port = FakeDailySummaryReadPort()
    handler = GetDailySummaryHandler(read_port, cache)

    dto = await handler.handle(GetDailySummaryQuery(user_id=user_id, summary_date=SUMMARY_DATE))
    assert dto.total_calories_kcal == 500.0


async def test_cache_miss_populates_cache_from_read_port():
    user_id = uuid.uuid4()
    cache = FakeDailySummaryCachePort()
    read_port = FakeDailySummaryReadPort()
    read_port.rows[(user_id, SUMMARY_DATE)] = _row()
    handler = GetDailySummaryHandler(read_port, cache)

    dto = await handler.handle(GetDailySummaryQuery(user_id=user_id, summary_date=SUMMARY_DATE))
    assert dto.total_calories_kcal == 500.0
    assert cache.cache[(user_id, SUMMARY_DATE)] == _row()


async def test_no_row_yet_returns_zeroed_summary():
    user_id = uuid.uuid4()
    cache = FakeDailySummaryCachePort()
    read_port = FakeDailySummaryReadPort()
    handler = GetDailySummaryHandler(read_port, cache)

    dto = await handler.handle(GetDailySummaryQuery(user_id=user_id, summary_date=SUMMARY_DATE))
    assert dto.total_calories_kcal == 0.0
    assert dto.fasting_windows_ended == 0
