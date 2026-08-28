"""PreferencesRepositoryPort -- Postgres adapter:
postgres_preferences_repository.py."""

from __future__ import annotations

import uuid
from typing import Protocol

from domain.entities.notification_preference import NotificationPreference


class PreferencesRepositoryPort(Protocol):
    async def get_all(self, user_id: uuid.UUID) -> list[NotificationPreference]: ...

    async def get_category(
        self, user_id: uuid.UUID, category_name: str
    ) -> NotificationPreference | None: ...

    async def upsert(self, preference: NotificationPreference) -> None: ...
