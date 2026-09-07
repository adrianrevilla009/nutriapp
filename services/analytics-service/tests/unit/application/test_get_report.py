from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

from application.errors import NotEntitledError
from application.queries.get_report import GetReportHandler, GetReportQuery
from tests.fixtures.factories import (
    FakeDailyLogSummaryRepository,
    FakeEntitlementCacheRepository,
    FakeEntitlementCheckPort,
    FakeExportAuditRepository,
    FakeMicronutrientWindowRepository,
)

START = date(2026, 6, 1)
END = date(2026, 6, 8)
NOW = datetime(2026, 6, 8, tzinfo=timezone.utc)


def _handler(cache, check, daily=None, window=None, audit=None):
    return GetReportHandler(
        daily or FakeDailyLogSummaryRepository(),
        window or FakeMicronutrientWindowRepository(),
        cache,
        check,
        audit or FakeExportAuditRepository(),
        now_fn=lambda: NOW,
    )


async def test_entitled_cache_hit_returns_csv_and_records_audit_exactly_once():
    user_id = uuid.uuid4()
    daily = FakeDailyLogSummaryRepository()
    await daily.apply_food_entry(uuid.uuid4(), user_id, START, 2000.0, 100.0, 200.0, 60.0)
    cache = FakeEntitlementCacheRepository(seed={user_id: True})
    check = FakeEntitlementCheckPort()
    audit = FakeExportAuditRepository()
    handler = _handler(cache, check, daily=daily, audit=audit)

    result = await handler.handle(
        GetReportQuery(user_id=user_id, report_type="full", start_date=START, end_date=END)
    )

    assert result.csv_content.startswith("#")
    assert "row_count=1" in result.csv_content.splitlines()[0]
    assert "daily_log_summary" in result.csv_content
    assert len(audit.records) == 1
    assert audit.records[0]["row_count"] == 1

    # Calling again with the exact same request logs a SECOND audit record --
    # exports are never deduplicated like event-consumption idempotency.
    await handler.handle(
        GetReportQuery(user_id=user_id, report_type="full", start_date=START, end_date=END)
    )
    assert len(audit.records) == 2


async def test_unentitled_cache_hit_rejected_before_any_data_read_or_audit_write():
    user_id = uuid.uuid4()
    daily = FakeDailyLogSummaryRepository()
    cache = FakeEntitlementCacheRepository(seed={user_id: False})
    check = FakeEntitlementCheckPort()
    audit = FakeExportAuditRepository()
    handler = _handler(cache, check, daily=daily, audit=audit)

    with pytest.raises(NotEntitledError):
        await handler.handle(
            GetReportQuery(user_id=user_id, report_type="full", start_date=START, end_date=END)
        )

    assert audit.records == []


async def test_cache_miss_falls_back_and_never_writes_back_to_cache():
    user_id = uuid.uuid4()
    cache = FakeEntitlementCacheRepository(seed={})
    check = FakeEntitlementCheckPort(result=True)
    handler = _handler(cache, check)

    await handler.handle(
        GetReportQuery(user_id=user_id, report_type="full", start_date=START, end_date=END)
    )

    assert check.calls == [user_id]
    assert cache.upsert_calls == 0
