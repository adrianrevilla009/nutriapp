"""QuietHoursWindow -- a user's non-transactional-push quiet hours,
default 22:00-08:00 local time, user-adjustable (docs/notifications.md
section 2). Correctly handles a window that crosses midnight.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

DEFAULT_QUIET_HOURS_START = time(22, 0)
DEFAULT_QUIET_HOURS_END = time(8, 0)
DEFAULT_TIMEZONE = "UTC"


class AmbiguousQuietHoursWindowError(ValueError):
    """Raised when start == end -- ambiguous "always quiet"/"never quiet"."""


@dataclass(frozen=True, slots=True)
class QuietHoursWindow:
    start: time
    end: time
    tz: str = DEFAULT_TIMEZONE

    def __post_init__(self) -> None:
        if self.start == self.end:
            raise AmbiguousQuietHoursWindowError(
                "A quiet-hours window with start == end is ambiguous."
            )

    def contains(self, at: datetime) -> bool:
        local_time = at.astimezone(ZoneInfo(self.tz)).time()
        if self.start < self.end:
            return self.start <= local_time < self.end
        # Crosses midnight (e.g. 22:00-08:00): "inside" is everything from
        # `start` to midnight, plus everything from midnight to `end`.
        return local_time >= self.start or local_time < self.end
