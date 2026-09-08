from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

from application.errors import InvalidReportRequestError, NotEntitledError
from application.queries.get_report import GetReportHandler, GetReportQuery
from domain.value_objects.export_outcome import ExportOutcome
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
        GetReportQuery(
            user_id=user_id,
            report_type="full",
            start_date=START,
            end_date=END,
            correlation_id="corr-success-1",
        )
    )

    assert result.csv_content.startswith("#")
    assert "row_count=1" in result.csv_content.splitlines()[0]
    assert "daily_log_summary" in result.csv_content
    assert len(audit.records) == 1
    record = audit.records[0]
    assert record["row_count"] == 1
    assert record["outcome"] == ExportOutcome.SUCCESS
    assert record["actor_id"] == user_id
    assert record["action"] == "export_report"
    assert record["target_type"] == "full"
    assert record["target_id"] == f"{START.isoformat()}..{END.isoformat()}"
    assert record["correlation_id"] == "corr-success-1"
    assert record["rejection_reason"] is None

    # Calling again with the exact same request logs a SECOND audit record --
    # exports are never deduplicated like event-consumption idempotency.
    await handler.handle(
        GetReportQuery(user_id=user_id, report_type="full", start_date=START, end_date=END)
    )
    assert len(audit.records) == 2


async def test_unentitled_cache_hit_rejected_before_any_data_read_but_audit_logged():
    """A rejected export attempt must still be audited (docs/observability-
    and-audit.md section 4.1: "data export requests" -- not just
    successful ones), but the report-data repositories must never be
    touched for a request that never passed the entitlement gate."""
    user_id = uuid.uuid4()
    daily = FakeDailyLogSummaryRepository()
    cache = FakeEntitlementCacheRepository(seed={user_id: False})
    check = FakeEntitlementCheckPort()
    audit = FakeExportAuditRepository()
    handler = _handler(cache, check, daily=daily, audit=audit)

    with pytest.raises(NotEntitledError):
        await handler.handle(
            GetReportQuery(
                user_id=user_id,
                report_type="full",
                start_date=START,
                end_date=END,
                correlation_id="corr-rejected-1",
            )
        )

    assert daily.list_window_call_count == 0
    assert len(audit.records) == 1
    record = audit.records[0]
    assert record["outcome"] == ExportOutcome.REJECTED
    assert record["rejection_reason"] == "not_entitled"
    assert record["row_count"] == 0
    assert record["actor_id"] == user_id
    assert record["correlation_id"] == "corr-rejected-1"


async def test_invalid_date_range_rejected_and_audited_before_any_data_read():
    user_id = uuid.uuid4()
    daily = FakeDailyLogSummaryRepository()
    cache = FakeEntitlementCacheRepository(seed={user_id: True})
    check = FakeEntitlementCheckPort()
    audit = FakeExportAuditRepository()
    handler = _handler(cache, check, daily=daily, audit=audit)

    with pytest.raises(InvalidReportRequestError):
        await handler.handle(
            GetReportQuery(user_id=user_id, report_type="full", start_date=END, end_date=START)
        )

    assert daily.list_window_call_count == 0
    assert check.calls == []  # rejected before the entitlement check even runs
    assert len(audit.records) == 1
    record = audit.records[0]
    assert record["outcome"] == ExportOutcome.REJECTED
    assert record["rejection_reason"] == "invalid_date_range"


async def test_window_exceeding_max_days_rejected_and_audited():
    user_id = uuid.uuid4()
    cache = FakeEntitlementCacheRepository(seed={user_id: True})
    check = FakeEntitlementCheckPort()
    audit = FakeExportAuditRepository()
    handler = _handler(cache, check, audit=audit)

    with pytest.raises(InvalidReportRequestError):
        await handler.handle(
            GetReportQuery(
                user_id=user_id,
                report_type="full",
                start_date=date(2020, 1, 1),
                end_date=date(2026, 6, 8),
            )
        )

    assert len(audit.records) == 1
    assert audit.records[0]["outcome"] == ExportOutcome.REJECTED
    assert audit.records[0]["rejection_reason"] == "window_exceeds_max_days"


async def test_repeated_rejected_attempts_each_produce_their_own_audit_record():
    """Idempotency requirement is for event *consumption*, not for audit
    writes -- every request, including a flood of repeated rejected probes
    against the same window, logs its own record (test-plan section 2)."""
    user_id = uuid.uuid4()
    cache = FakeEntitlementCacheRepository(seed={user_id: False})
    check = FakeEntitlementCheckPort()
    audit = FakeExportAuditRepository()
    handler = _handler(cache, check, audit=audit)

    for _ in range(3):
        with pytest.raises(NotEntitledError):
            await handler.handle(
                GetReportQuery(user_id=user_id, report_type="full", start_date=START, end_date=END)
            )

    assert len(audit.records) == 3
    assert all(r["outcome"] == ExportOutcome.REJECTED for r in audit.records)


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
