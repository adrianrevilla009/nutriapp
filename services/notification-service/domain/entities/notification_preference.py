"""NotificationPreference -- one row per (user_id, push category)
(implementation plan section 3): opt-in/out per category plus that
category's quiet-hours window. Never constructed for a transactional
category -- NotificationCategory.push()'s own validation already
enforces this at the type level (test-plan section 1)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.value_objects.notification_category import NotificationCategory
from domain.value_objects.quiet_hours_window import (
    DEFAULT_QUIET_HOURS_END,
    DEFAULT_QUIET_HOURS_START,
    DEFAULT_TIMEZONE,
    QuietHoursWindow,
)


@dataclass(slots=True)
class NotificationPreference:
    user_id: uuid.UUID
    category: NotificationCategory
    push_enabled: bool = True
    quiet_hours: QuietHoursWindow = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.quiet_hours is None:
            self.quiet_hours = QuietHoursWindow(
                start=DEFAULT_QUIET_HOURS_START,
                end=DEFAULT_QUIET_HOURS_END,
                tz=DEFAULT_TIMEZONE,
            )
