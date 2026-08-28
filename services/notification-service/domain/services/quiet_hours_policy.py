"""quiet_hours_policy -- pure domain rule (docs/notifications.md section
2): a non-transactional send during the user's quiet hours is delayed to
the next allowed window, never dropped. Structurally refuses to apply to
transactional categories (test-plan section 1) -- those are never
quiet-hours-gated, so calling this policy with one is a programming error,
not a business scenario to silently handle.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from domain.value_objects.notification_category import NotificationCategory
from domain.value_objects.quiet_hours_window import QuietHoursWindow


class QuietHoursNotApplicableToTransactionalCategoryError(ValueError):
    """Raised if this policy is ever invoked for a transactional category."""


def next_allowed_send_time(
    category: NotificationCategory, window: QuietHoursWindow, now: datetime
) -> datetime:
    if category.is_transactional:
        raise QuietHoursNotApplicableToTransactionalCategoryError(
            "Quiet hours never apply to a transactional category."
        )
    if not window.contains(now):
        return now

    tz = ZoneInfo(window.tz)
    local_now = now.astimezone(tz)
    candidate = local_now.replace(
        hour=window.end.hour,
        minute=window.end.minute,
        second=window.end.second,
        microsecond=0,
    )
    if candidate <= local_now:
        candidate = candidate + timedelta(days=1)
    return candidate.astimezone(now.tzinfo)
