from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from domain.services import goal_policy
from domain.services.goal_policy import MissingGoalTargetDateError
from domain.value_objects.goal_target import GoalTarget, InvalidGoalTargetError
from domain.value_objects.goal_type import GoalType

NOW = datetime(2026, 8, 24, tzinfo=timezone.utc)
FUTURE_DATE = date(2026, 12, 1)


def test_lose_goal_target_below_latest_weight_accepted():
    target = GoalTarget(target_value=65.0, target_date=FUTURE_DATE, now=NOW)
    goal_policy.validate(GoalType.LOSE, target, latest_weight_kg=70.0, now=NOW)


def test_lose_goal_target_at_or_above_latest_weight_rejected():
    target = GoalTarget(target_value=70.0, target_date=FUTURE_DATE, now=NOW)
    with pytest.raises(InvalidGoalTargetError):
        goal_policy.validate(GoalType.LOSE, target, latest_weight_kg=70.0, now=NOW)


def test_lose_goal_with_no_weight_recorded_skips_comparison():
    target = GoalTarget(target_value=65.0, target_date=FUTURE_DATE, now=NOW)
    goal_policy.validate(GoalType.LOSE, target, latest_weight_kg=None, now=NOW)


def test_gain_goal_target_above_latest_weight_accepted():
    target = GoalTarget(target_value=75.0, target_date=FUTURE_DATE, now=NOW)
    goal_policy.validate(GoalType.GAIN, target, latest_weight_kg=70.0, now=NOW)


def test_gain_goal_target_at_or_below_latest_weight_rejected():
    target = GoalTarget(target_value=70.0, target_date=FUTURE_DATE, now=NOW)
    with pytest.raises(InvalidGoalTargetError):
        goal_policy.validate(GoalType.GAIN, target, latest_weight_kg=70.0, now=NOW)


def test_gain_goal_with_no_weight_recorded_skips_comparison():
    target = GoalTarget(target_value=75.0, target_date=FUTURE_DATE, now=NOW)
    goal_policy.validate(GoalType.GAIN, target, latest_weight_kg=None, now=NOW)


def test_maintain_goal_allows_omitted_target_fields():
    target = GoalTarget(target_value=None, target_date=None)
    goal_policy.validate(GoalType.MAINTAIN, target, latest_weight_kg=70.0, now=NOW)


def test_maintain_goal_with_given_fields_skips_comparison():
    target = GoalTarget(target_value=200.0, target_date=FUTURE_DATE, now=NOW)
    goal_policy.validate(GoalType.MAINTAIN, target, latest_weight_kg=70.0, now=NOW)


def test_lose_goal_missing_target_date_raises():
    target = GoalTarget(target_value=65.0, target_date=None)
    with pytest.raises(MissingGoalTargetDateError):
        goal_policy.validate(GoalType.LOSE, target, latest_weight_kg=70.0, now=NOW)


def test_gain_goal_missing_target_date_raises():
    target = GoalTarget(target_value=75.0, target_date=None)
    with pytest.raises(MissingGoalTargetDateError):
        goal_policy.validate(GoalType.GAIN, target, latest_weight_kg=70.0, now=NOW)


def test_lose_goal_missing_target_value_raises():
    target = GoalTarget(target_value=None, target_date=FUTURE_DATE, now=NOW)
    with pytest.raises(InvalidGoalTargetError):
        goal_policy.validate(GoalType.LOSE, target, latest_weight_kg=70.0, now=NOW)
