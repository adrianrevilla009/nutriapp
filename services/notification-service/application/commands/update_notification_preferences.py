"""UpdateNotificationPreferencesCommand + handler -- backs
PATCH /api/v1/notifications/preferences (implementation plan section 1,
acceptance criterion 3). Rejects any attempt to set preferences/quiet
hours for a transactional category: NotificationCategory.push()'s own
validation already enforces "push categories only" at construction, which
is exactly the structural enforcement test-plan section 1 asks for at
this application-command boundary.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import time

from application.errors import InvalidPreferenceUpdateError
from domain.entities.notification_preference import NotificationPreference
from domain.ports.preferences_repository_port import PreferencesRepositoryPort
from domain.value_objects.notification_category import (
    InvalidNotificationCategoryError,
    NotificationCategory,
)
from domain.value_objects.quiet_hours_window import (
    AmbiguousQuietHoursWindowError,
    QuietHoursWindow,
)


@dataclass(frozen=True, slots=True)
class UpdateNotificationPreferencesCommand:
    user_id: uuid.UUID
    category: str
    push_enabled: bool
    quiet_hours_start: time
    quiet_hours_end: time
    timezone: str


class UpdateNotificationPreferencesHandler:
    def __init__(self, preferences: PreferencesRepositoryPort) -> None:
        self._preferences = preferences

    async def handle(self, command: UpdateNotificationPreferencesCommand) -> NotificationPreference:
        try:
            category = NotificationCategory.push(command.category)
        except InvalidNotificationCategoryError as exc:
            raise InvalidPreferenceUpdateError(str(exc)) from exc

        try:
            quiet_hours = QuietHoursWindow(
                start=command.quiet_hours_start, end=command.quiet_hours_end, tz=command.timezone
            )
        except AmbiguousQuietHoursWindowError as exc:
            raise InvalidPreferenceUpdateError(str(exc)) from exc

        preference = NotificationPreference(
            user_id=command.user_id,
            category=category,
            push_enabled=command.push_enabled,
            quiet_hours=quiet_hours,
        )
        await self._preferences.upsert(preference)
        return preference
