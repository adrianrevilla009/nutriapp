from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from domain.value_objects.goal_target import GoalTarget, InvalidGoalTargetError


def test_future_target_date_accepted():
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)
    target = GoalTarget(target_value=65.0, target_date=date(2026, 12, 1), now=now)
    assert target.target_date == date(2026, 12, 1)


def test_past_target_date_raises():
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)
    with pytest.raises(InvalidGoalTargetError):
        GoalTarget(target_value=65.0, target_date=date(2026, 1, 1), now=now)


def test_today_target_date_raises():
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)
    with pytest.raises(InvalidGoalTargetError):
        GoalTarget(target_value=65.0, target_date=now.date(), now=now)


def test_none_target_date_accepted():
    target = GoalTarget(target_value=None, target_date=None)
    assert target.target_date is None
