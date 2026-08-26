"""fasting_overlap_policy -- enforces the "no overlapping fasting windows"
invariant (implementation plan section 9.2, resolved: simple open-window
check). Pure function, no I/O, testable in isolation from the aggregate
(test-plan section 1's "fasting_overlap_policy" case group).

Reject a new FastingWindowStarted if the user's aggregate already has a
window with started_at set and no ended_at (O(1) against derived state).
Full interval-overlap checking against historical closed windows is an
explicitly deferred future extension (implementation plan section 9.2),
not designed here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class WindowState:
    window_id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None

    @property
    def is_open(self) -> bool:
        return self.ended_at is None


def is_start_allowed(windows: list[WindowState]) -> bool:
    """True unless `windows` contains an already-open window."""
    return not any(window.is_open for window in windows)
