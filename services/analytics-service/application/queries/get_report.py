"""GetReportHandler -- backs `GET /api/v1/analytics/reports/{report_type}`
and the CSV data-export endpoint (implementation plan section 1
acceptance criterion 4; format decided in section 9 addendum, resolution
4: CSV only for v1, `daily_log_summary` + `micronutrient_window` rows for
the requested date range). **Pro-gated** -- entitlement checked
cache-first, falling back to `EntitlementCheckPort` only on a genuine
cache miss (`application.entitlement_check.is_user_entitled`). The
entitlement check itself still runs BEFORE any report-data repository
read (cheapest-check-first, mirrors `recipe-service`'s/`social-service`'s
precedent) -- only the audit write ordering changed: every rejection
(invalid request OR not entitled) is now audit-logged too, right at the
point the rejection is decided, still before any report-data repository
read (docs/observability-and-audit.md section 4.1 mandates auditing
"data export requests", not just successful ones -- a security review
found repeated unauthorized/probing attempts left zero audit trail).

Every call to `handle` -- success or rejection -- is recorded in
`export_audit_log` exactly once; not deduplicated like event-consumption
idempotency, every request is its own audit fact (test-plan section 2's
explicit rule, extended to cover rejections).

The CSV carries a leading manifest comment line stating row count and
date range (implementation plan section 9 addendum's CSV-manifest
resolution, approved 2026-09-07) -- CLAUDE.md's "never present a
statistic without sample size and window" rule, applied to an export."""

from __future__ import annotations

import csv
import io
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone

from application.entitlement_check import is_user_entitled
from application.errors import InvalidReportRequestError, NotEntitledError
from domain.ports.daily_log_summary_repository_port import DailyLogSummaryRepositoryPort
from domain.ports.entitlement_cache_repository_port import EntitlementCacheRepositoryPort
from domain.ports.entitlement_check_port import EntitlementCheckPort
from domain.ports.export_audit_repository_port import ExportAuditRepositoryPort
from domain.ports.micronutrient_window_repository_port import MicronutrientWindowRepositoryPort
from domain.services.trend_calculator import DailyMacroTotals
from domain.value_objects.export_outcome import ExportOutcome
from domain.value_objects.report_period import ReportPeriod

MAX_REPORT_WINDOW_DAYS = 365
EXPORT_FORMAT = "csv"
EXPORT_ACTION = "export_report"


@dataclass(frozen=True, slots=True)
class GetReportQuery:
    user_id: uuid.UUID
    report_type: str
    start_date: date
    end_date: date
    correlation_id: str = ""


@dataclass(frozen=True, slots=True)
class ReportResult:
    csv_content: str
    period: ReportPeriod


def _build_csv(
    report_type: str,
    period: ReportPeriod,
    daily_rows: Sequence[DailyMacroTotals],
    micronutrient_rows: Sequence[dict[str, object]],
) -> str:
    buffer = io.StringIO()
    buffer.write(
        f"# analytics-service export | report_type={report_type} | "
        f"date_range={period.start_date.isoformat()}..{period.end_date.isoformat()} | "
        f"window_days={period.window_days} | row_count={period.row_count}\n"
    )

    writer = csv.writer(buffer)
    writer.writerow(["table", "date", "calories_kcal", "protein_g", "carbs_g", "fat_g", "water_ml"])
    for row in daily_rows:
        writer.writerow(
            [
                "daily_log_summary",
                row.on_date.isoformat(),
                row.calories_kcal,
                row.protein_g,
                row.carbs_g,
                row.fat_g,
                row.water_ml,
            ]
        )

    buffer.write("\n")
    writer.writerow(["table", "date", "nutrient", "value", "target_min"])
    for nutrient_row in micronutrient_rows:
        writer.writerow(
            [
                "micronutrient_window",
                nutrient_row["on_date"],
                nutrient_row["nutrient"],
                nutrient_row["value"],
                nutrient_row["target_min"],
            ]
        )

    return buffer.getvalue()


class GetReportHandler:
    def __init__(
        self,
        daily_log_summary: DailyLogSummaryRepositoryPort,
        micronutrient_window: MicronutrientWindowRepositoryPort,
        entitlement_cache: EntitlementCacheRepositoryPort,
        entitlement_check: EntitlementCheckPort,
        export_audit: ExportAuditRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._daily_log_summary = daily_log_summary
        self._micronutrient_window = micronutrient_window
        self._entitlement_cache = entitlement_cache
        self._entitlement_check = entitlement_check
        self._export_audit = export_audit
        self._now_fn = now_fn

    def _target_id(self, query: GetReportQuery) -> str:
        return f"{query.start_date.isoformat()}..{query.end_date.isoformat()}"

    async def _audit(
        self,
        query: GetReportQuery,
        outcome: ExportOutcome,
        row_count: int,
        rejection_reason: str | None = None,
    ) -> None:
        await self._export_audit.record(
            user_id=query.user_id,
            report_type=query.report_type,
            requested_at=self._now_fn(),
            export_format=EXPORT_FORMAT,
            start_date=query.start_date,
            end_date=query.end_date,
            row_count=row_count,
            outcome=outcome,
            actor_id=query.user_id,
            action=EXPORT_ACTION,
            target_type=query.report_type,
            target_id=self._target_id(query),
            correlation_id=query.correlation_id,
            rejection_reason=rejection_reason,
        )

    async def handle(self, query: GetReportQuery) -> ReportResult:
        if query.start_date > query.end_date:
            await self._audit(
                query, ExportOutcome.REJECTED, row_count=0, rejection_reason="invalid_date_range"
            )
            raise InvalidReportRequestError("start_date must be <= end_date.")
        window_days = (query.end_date - query.start_date).days + 1
        if window_days > MAX_REPORT_WINDOW_DAYS:
            await self._audit(
                query,
                ExportOutcome.REJECTED,
                row_count=0,
                rejection_reason="window_exceeds_max_days",
            )
            raise InvalidReportRequestError(
                f"Requested window ({window_days} days) exceeds the maximum "
                f"of {MAX_REPORT_WINDOW_DAYS} days."
            )

        entitled = await is_user_entitled(
            query.user_id, self._entitlement_cache, self._entitlement_check
        )
        if not entitled:
            await self._audit(
                query, ExportOutcome.REJECTED, row_count=0, rejection_reason="not_entitled"
            )
            raise NotEntitledError("User is not entitled to generate reports or export data.")

        daily_rows = await self._daily_log_summary.list_window(
            query.user_id, query.start_date, query.end_date
        )
        micronutrient_rows = await self._micronutrient_window.list_window(
            query.user_id, query.start_date, query.end_date
        )
        row_count = len(daily_rows) + len(micronutrient_rows)
        period = ReportPeriod(
            start_date=query.start_date, end_date=query.end_date, row_count=row_count
        )

        csv_content = _build_csv(query.report_type, period, daily_rows, micronutrient_rows)

        await self._audit(query, ExportOutcome.SUCCESS, row_count=row_count)

        return ReportResult(csv_content=csv_content, period=period)
