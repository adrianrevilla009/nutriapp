"""GoalTarget value object -- bundles the optional target value and target
date for a goal. Zero framework imports (ADR-0001); "now" is injected so
this stays deterministic and testable without a hidden clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone


class InvalidGoalTargetError(Exception):
    """Raised when a GoalTarget's fields are internally inconsistent, e.g.
    a target_date that is not in the future."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class GoalTarget:
    target_value: float | None = None
    target_date: date | None = None
    now: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if self.target_date is not None and self.target_date <= self.now.date():
            raise InvalidGoalTargetError("target_date must be in the future.")
