"""PendingDispatchStatus -- the lifecycle of a `pending_push_dispatch` row
(a one-shot push notification deferred past a quiet-hours window, see
domain/entities/pending_push_dispatch.py). Kept as its own narrow value
object rather than reusing ReminderStatus (a periodic reminder's own
lifecycle) or DeliveryStatus (a channel send attempt's own lifecycle) --
this table's semantics are deliberately not overloaded onto either.
"""

from __future__ import annotations

from enum import Enum


class PendingDispatchStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    SUPPRESSED = "suppressed"
