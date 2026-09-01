"""NotificationCategory -- channel/category mismatch validation
(test-plan section 1)."""

from __future__ import annotations

import pytest

from domain.value_objects.notification_category import (
    EMAIL_CATEGORIES,
    PUSH_CATEGORIES,
    InvalidNotificationCategoryError,
    NotificationCategory,
)


def test_push_categories_are_accepted():
    for name in ("fasting", "meal", "water", "new_follower"):
        category = NotificationCategory.push(name)
        assert category.name == name
        assert category.is_transactional is False


def test_new_follower_push_category_does_not_collide_with_any_email_category():
    # social-service's UserFollowed-triggered push (implementation plan
    # section 6 / test-plan section 6): "new_follower" must be a push-only
    # category name, never reusable as a transactional email category.
    assert "new_follower" in PUSH_CATEGORIES
    assert "new_follower" not in EMAIL_CATEGORIES
    with pytest.raises(InvalidNotificationCategoryError):
        NotificationCategory.email("new_follower")


def test_email_categories_are_accepted():
    for name in ("verification", "password_reset", "new_device_alert"):
        category = NotificationCategory.email(name)
        assert category.name == name
        assert category.is_transactional is True


def test_email_category_rejected_as_push_category():
    with pytest.raises(InvalidNotificationCategoryError):
        NotificationCategory.push("verification")


def test_push_category_rejected_as_email_category():
    with pytest.raises(InvalidNotificationCategoryError):
        NotificationCategory.email("fasting")


def test_unknown_category_name_rejected():
    with pytest.raises(InvalidNotificationCategoryError):
        NotificationCategory.push("not_a_real_category")
