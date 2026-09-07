"""A single day's contribution to a trend -- the smallest unit
`trend_calculator.py`'s pure functions fold over. Not a repository row
shape; `daily_log_summary`/`micronutrient_window` rows are mapped into
this by the relevant Postgres repository before reaching the domain
layer (ADR-0001: the domain layer never sees an ORM row)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class TrendPoint:
    on_date: date
    value: float
