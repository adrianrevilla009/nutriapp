"""PostgresPreferencesRepository -- round-trip persistence (test-plan
section 2)."""

from __future__ import annotations

import uuid
from datetime import time

from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.notification_preference import NotificationPreference
from domain.value_objects.notification_category import NotificationCategory
from domain.value_objects.quiet_hours_window import QuietHoursWindow
from infrastructure.persistence.postgres_preferences_repository import (
    PostgresPreferencesRepository,
)


async def test_upsert_then_get_category(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresPreferencesRepository(session)
        user_id = uuid.uuid4()
        preference = NotificationPreference(
            user_id=user_id,
            category=NotificationCategory.push("meal"),
            push_enabled=False,
            quiet_hours=QuietHoursWindow(start=time(23, 0), end=time(6, 0), tz="Europe/Madrid"),
        )
        await repo.upsert(preference)
        await session.commit()

        fetched = await repo.get_category(user_id, "meal")
        assert fetched is not None
        assert fetched.push_enabled is False
        assert fetched.quiet_hours.tz == "Europe/Madrid"


async def test_get_all_returns_every_category_for_a_user(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresPreferencesRepository(session)
        user_id = uuid.uuid4()
        await repo.upsert(
            NotificationPreference(user_id=user_id, category=NotificationCategory.push("meal"))
        )
        await repo.upsert(
            NotificationPreference(user_id=user_id, category=NotificationCategory.push("water"))
        )
        await session.commit()

        all_prefs = await repo.get_all(user_id)
        assert {p.category.name for p in all_prefs} == {"meal", "water"}
