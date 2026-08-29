"""PostgresPreferencesRepository -- implements PreferencesRepositoryPort."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.notification_preference import NotificationPreference
from domain.value_objects.notification_category import NotificationCategory
from domain.value_objects.quiet_hours_window import QuietHoursWindow
from infrastructure.persistence.models import NotificationPreferenceModel


def _to_entity(row: NotificationPreferenceModel) -> NotificationPreference:
    return NotificationPreference(
        user_id=row.user_id,
        category=NotificationCategory.push(row.category),
        push_enabled=row.push_enabled,
        quiet_hours=QuietHoursWindow(
            start=row.quiet_hours_start, end=row.quiet_hours_end, tz=row.timezone
        ),
    )


class PostgresPreferencesRepository:
    """Implements domain.ports.preferences_repository_port.PreferencesRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self, user_id: uuid.UUID) -> list[NotificationPreference]:
        result = await self._session.execute(
            select(NotificationPreferenceModel).where(
                NotificationPreferenceModel.user_id == user_id
            )
        )
        return [_to_entity(row) for row in result.scalars()]

    async def get_category(
        self, user_id: uuid.UUID, category_name: str
    ) -> NotificationPreference | None:
        result = await self._session.execute(
            select(NotificationPreferenceModel).where(
                NotificationPreferenceModel.user_id == user_id,
                NotificationPreferenceModel.category == category_name,
            )
        )
        row = result.scalar_one_or_none()
        return None if row is None else _to_entity(row)

    async def upsert(self, preference: NotificationPreference) -> None:
        stmt = insert(NotificationPreferenceModel).values(
            user_id=preference.user_id,
            category=preference.category.name,
            push_enabled=preference.push_enabled,
            quiet_hours_start=preference.quiet_hours.start,
            quiet_hours_end=preference.quiet_hours.end,
            timezone=preference.quiet_hours.tz,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "category"],
            set_={
                "push_enabled": preference.push_enabled,
                "quiet_hours_start": preference.quiet_hours.start,
                "quiet_hours_end": preference.quiet_hours.end,
                "timezone": preference.quiet_hours.tz,
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()
