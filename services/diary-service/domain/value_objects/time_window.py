"""TimeWindow -- start/end + overlap predicate helper, used by the
FastingWindow aggregate/fasting_overlap_policy (implementation plan
section 9.2's resolved simple open-window check)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class InvalidTimeWindowError(Exception):
    """Raised when end is before start."""


@dataclass(frozen=True, slots=True)
class TimeWindow:
    start: datetime
    end: datetime | None = None

    def __post_init__(self) -> None:
        if self.end is not None and self.end < self.start:
            raise InvalidTimeWindowError("end must not be before start.")

    @property
    def is_open(self) -> bool:
        return self.end is None
