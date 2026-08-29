"""quiet_hours_policy -- test-plan section 1: delay inside quiet hours,
immediate outside, structural refusal for transactional categories."""

from __future__ import annotations

from datetime import datetime, time, timezone

import pytest

from domain.services.quiet_hours_policy import (
    QuietHoursNotApplicableToTransactionalCategoryError,
    next_allowed_send_time,
)
from domain.value_objects.notification_category import NotificationCategory
from domain.value_objects.quiet_hours_window import QuietHoursWindow

_WINDOW = QuietHoursWindow(start=time(22, 0), end=time(8, 0), tz="UTC")
_PUSH_CATEGORY = NotificationCategory.push("fasting")


def test_inside_quiet_hours_delays_to_next_allowed_window():
    now = datetime(2026, 8, 28, 23, 0, tzinfo=timezone.utc)
    result = next_allowed_send_time(_PUSH_CATEGORY, _WINDOW, now)
    assert result > now
    assert result.astimezone(timezone.utc).time() == time(8, 0)
    assert _WINDOW.contains(result) is False


def test_outside_quiet_hours_sends_immediately():
    now = datetime(2026, 8, 28, 10, 0, tzinfo=timezone.utc)
    result = next_allowed_send_time(_PUSH_CATEGORY, _WINDOW, now)
    assert result == now


def test_transactional_category_is_structurally_refused():
    now = datetime(2026, 8, 28, 23, 0, tzinfo=timezone.utc)
    transactional = NotificationCategory.email("verification")
    with pytest.raises(QuietHoursNotApplicableToTransactionalCategoryError):
        next_allowed_send_time(transactional, _WINDOW, now)
