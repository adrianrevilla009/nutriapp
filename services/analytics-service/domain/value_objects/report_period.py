"""The requested/served window for a CSV report or export
(`GetReportHandler`/`ExportReportHandler`) -- carries `row_count` so the
CSV's leading manifest line (implementation plan section 9 addendum,
CSV-manifest resolution, test-plan section 3) always states its sample
size, same disclosure rule as every other computed metric in this
service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


class InvalidReportPeriodError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ReportPeriod:
    start_date: date
    end_date: date
    row_count: int

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise InvalidReportPeriodError("start_date must be <= end_date.")
        if self.row_count < 0:
            raise InvalidReportPeriodError("row_count must be >= 0.")

    @property
    def window_days(self) -> int:
        return (self.end_date - self.start_date).days + 1
