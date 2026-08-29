"""ReminderStatus -- the status of a `reminder_schedule` projection row.
Distinct from DeliveryStatus (which tracks a channel send attempt, not a
scheduled reminder's own lifecycle)."""

from __future__ import annotations

from enum import Enum


class ReminderStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    SUPPRESSED = "suppressed"
