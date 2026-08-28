"""due_and_stale_policy -- pure domain rule (docs/notifications.md section
2): a reminder whose relevance window has passed is suppressed rather than
sent late; a reminder not yet due takes no action; a reminder currently in
its due window should be sent. Zero I/O.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum


class ReminderEvaluation(str, Enum):
    NOT_DUE = "not_due"
    DUE = "due"
    STALE = "stale"


def evaluate(due_at: datetime, relevance_expires_at: datetime, now: datetime) -> ReminderEvaluation:
    if now < due_at:
        return ReminderEvaluation.NOT_DUE
    if now > relevance_expires_at:
        return ReminderEvaluation.STALE
    return ReminderEvaluation.DUE
