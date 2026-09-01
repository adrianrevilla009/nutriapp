"""GetNotificationPreferencesHandler -- confirms the no-migration design
decision from /plans/social-service/implementation-plan.md section 7 holds
in practice, not just in theory: adding "new_follower" to PUSH_CATEGORIES
alone (no schema change) is enough for it to appear as a default
preference row for a user who has never explicitly set it (test-plan
section 6)."""

from __future__ import annotations

import uuid

from application.queries.get_notification_preferences import (
    GetNotificationPreferencesHandler,
    GetNotificationPreferencesQuery,
)
from domain.value_objects.notification_category import PUSH_CATEGORIES
from tests.fixtures.factories import FakePreferencesRepositoryPort


async def test_new_follower_appears_in_defaults_for_a_user_with_no_override():
    repo = FakePreferencesRepositoryPort()
    handler = GetNotificationPreferencesHandler(repo)
    user_id = uuid.uuid4()

    preferences = await handler.handle(GetNotificationPreferencesQuery(user_id=user_id))

    categories = {pref.category.name for pref in preferences}
    assert categories == set(PUSH_CATEGORIES)
    assert "new_follower" in categories
    new_follower_pref = next(p for p in preferences if p.category.name == "new_follower")
    assert new_follower_pref.push_enabled is True  # entity default, shown as the UI default


async def test_new_follower_explicit_override_is_returned_instead_of_the_default():
    repo = FakePreferencesRepositoryPort()
    user_id = uuid.uuid4()
    repo.seed(user_id, "new_follower", push_enabled=False)
    handler = GetNotificationPreferencesHandler(repo)

    preferences = await handler.handle(GetNotificationPreferencesQuery(user_id=user_id))

    new_follower_pref = next(p for p in preferences if p.category.name == "new_follower")
    assert new_follower_pref.push_enabled is False
