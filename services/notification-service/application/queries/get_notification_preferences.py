"""GetNotificationPreferencesHandler -- backs
GET /api/v1/notifications/preferences. Returns a default (push_enabled,
default quiet hours) row per known push category for any category the
user has never explicitly set, so the caller always sees a complete set.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.entities.notification_preference import NotificationPreference
from domain.ports.preferences_repository_port import PreferencesRepositoryPort
from domain.value_objects.notification_category import PUSH_CATEGORIES, NotificationCategory


@dataclass(frozen=True, slots=True)
class GetNotificationPreferencesQuery:
    user_id: uuid.UUID


class GetNotificationPreferencesHandler:
    def __init__(self, preferences: PreferencesRepositoryPort) -> None:
        self._preferences = preferences

    async def handle(self, query: GetNotificationPreferencesQuery) -> list[NotificationPreference]:
        existing = {
            pref.category.name: pref for pref in await self._preferences.get_all(query.user_id)
        }
        result: list[NotificationPreference] = []
        for category_name in sorted(PUSH_CATEGORIES):
            if category_name in existing:
                result.append(existing[category_name])
            else:
                result.append(
                    NotificationPreference(
                        user_id=query.user_id, category=NotificationCategory.push(category_name)
                    )
                )
        return result
