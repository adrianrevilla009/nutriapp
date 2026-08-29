"""UpdateNotificationPreferencesHandler -- test-plan section 1."""

from __future__ import annotations

import uuid
from datetime import time

import pytest

from application.commands.update_notification_preferences import (
    UpdateNotificationPreferencesCommand,
    UpdateNotificationPreferencesHandler,
)
from application.errors import InvalidPreferenceUpdateError
from application.queries.get_notification_preferences import (
    GetNotificationPreferencesHandler,
    GetNotificationPreferencesQuery,
)
from tests.fixtures.factories import FakePreferencesRepositoryPort


async def test_valid_update_is_persisted_and_returned_by_query():
    repo = FakePreferencesRepositoryPort()
    handler = UpdateNotificationPreferencesHandler(repo)
    user_id = uuid.uuid4()

    await handler.handle(
        UpdateNotificationPreferencesCommand(
            user_id=user_id,
            category="meal",
            push_enabled=False,
            quiet_hours_start=time(23, 0),
            quiet_hours_end=time(7, 0),
            timezone="Europe/Madrid",
        )
    )

    query_handler = GetNotificationPreferencesHandler(repo)
    preferences = await query_handler.handle(GetNotificationPreferencesQuery(user_id=user_id))
    meal_pref = next(p for p in preferences if p.category.name == "meal")
    assert meal_pref.push_enabled is False
    assert meal_pref.quiet_hours.tz == "Europe/Madrid"


async def test_transactional_category_is_rejected():
    repo = FakePreferencesRepositoryPort()
    handler = UpdateNotificationPreferencesHandler(repo)

    with pytest.raises(InvalidPreferenceUpdateError):
        await handler.handle(
            UpdateNotificationPreferencesCommand(
                user_id=uuid.uuid4(),
                category="verification",
                push_enabled=True,
                quiet_hours_start=time(22, 0),
                quiet_hours_end=time(8, 0),
                timezone="UTC",
            )
        )


async def test_malformed_quiet_hours_window_is_rejected():
    repo = FakePreferencesRepositoryPort()
    handler = UpdateNotificationPreferencesHandler(repo)

    with pytest.raises(InvalidPreferenceUpdateError):
        await handler.handle(
            UpdateNotificationPreferencesCommand(
                user_id=uuid.uuid4(),
                category="meal",
                push_enabled=True,
                quiet_hours_start=time(9, 0),
                quiet_hours_end=time(9, 0),
                timezone="UTC",
            )
        )
