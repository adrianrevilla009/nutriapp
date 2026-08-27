from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

from domain.entities.profile import (
    ConsentRequiredError,
    GoalAlreadyExistsError,
    NoExistingGoalError,
    Profile,
    UnsupportedMetricTypeError,
)
from domain.value_objects.goal_target import GoalTarget
from domain.value_objects.goal_type import GoalType
from domain.value_objects.weight_kg import WeightKg

USER_ID = uuid.uuid4()
NOW = datetime(2026, 8, 24, tzinfo=timezone.utc)


def _create_profile() -> Profile:
    profile, _event = Profile.create(USER_ID, correlation_id="corr-1")
    return profile


def test_rebuild_from_profile_created_only():
    profile, event = Profile.create(USER_ID, correlation_id="corr-1")
    rebuilt = Profile.rebuild([event])
    assert rebuilt.exists is True
    assert rebuilt.consent_granted is False
    assert rebuilt.weight_kg is None
    assert rebuilt.goal_type is None


def test_rebuild_with_consent_granted():
    profile = _create_profile()
    consent_event = profile.grant_consent(NOW, correlation_id="corr-2")
    rebuilt = Profile.rebuild([_profile_created_event(), consent_event])
    assert rebuilt.consent_granted is True


def _profile_created_event():
    _profile, event = Profile.create(USER_ID, correlation_id="corr-1")
    return event


def test_record_weight_before_consent_raises_and_produces_no_event():
    profile = _create_profile()
    weight = WeightKg(70.0)
    with pytest.raises(ConsentRequiredError):
        profile.record_weight(weight, NOW, correlation_id="corr-3")


def test_record_weight_after_consent_produces_event_and_updates_state():
    profile = _create_profile()
    profile.grant_consent(NOW, correlation_id="corr-2")
    event = profile.record_weight(WeightKg(70.0), NOW, correlation_id="corr-3")
    assert event.event_type == "WeightRecorded"
    assert profile.weight_kg == 70.0


def test_record_weight_twice_produces_two_events_first_unmodified():
    profile = _create_profile()
    profile.grant_consent(NOW, correlation_id="corr-2")
    first_event = profile.record_weight(WeightKg(70.0), NOW, correlation_id="corr-3")
    second_event = profile.record_weight(WeightKg(68.0), NOW, correlation_id="corr-4")
    assert first_event.payload["weight_kg"] == 70.0
    assert second_event.payload["weight_kg"] == 68.0
    assert profile.weight_kg == 68.0


@pytest.mark.parametrize(
    "metric_type,value",
    [("height", 175.0), ("age", 30), ("sex", "MALE"), ("activity_level", "ACTIVE")],
)
def test_record_body_metric_produces_matching_event(metric_type, value):
    profile = _create_profile()
    profile.grant_consent(NOW, correlation_id="corr-2")
    event = profile.record_body_metric(metric_type, value, NOW, correlation_id="corr-3")
    assert event.event_type == "BodyMetricRecorded"
    assert event.payload["metric_type"] == metric_type
    assert profile.body_metrics[metric_type] == value


def test_record_body_metric_unsupported_type_raises():
    profile = _create_profile()
    profile.grant_consent(NOW, correlation_id="corr-2")
    with pytest.raises(UnsupportedMetricTypeError):
        profile.record_body_metric("unknown", 1, NOW, correlation_id="corr-3")


def test_record_body_metric_before_consent_raises():
    profile = _create_profile()
    with pytest.raises(ConsentRequiredError):
        profile.record_body_metric("height", 175.0, NOW, correlation_id="corr-3")


def test_set_goal_on_profile_with_no_goal_produces_goal_set():
    profile = _create_profile()
    target = GoalTarget(target_value=65.0, target_date=date(2026, 12, 1), now=NOW)
    event = profile.set_goal(GoalType.LOSE, target, NOW, correlation_id="corr-5")
    assert event.event_type == "GoalSet"
    assert profile.goal_type == GoalType.LOSE


def test_set_goal_on_profile_with_existing_goal_raises():
    profile = _create_profile()
    target = GoalTarget(target_value=65.0, target_date=date(2026, 12, 1), now=NOW)
    profile.set_goal(GoalType.LOSE, target, NOW, correlation_id="corr-5")
    empty_target = GoalTarget()
    with pytest.raises(GoalAlreadyExistsError):
        profile.set_goal(GoalType.MAINTAIN, empty_target, NOW, correlation_id="corr-6")


def test_update_goal_on_profile_with_existing_goal_carries_previous_goal_type():
    profile = _create_profile()
    target = GoalTarget(target_value=65.0, target_date=date(2026, 12, 1), now=NOW)
    profile.set_goal(GoalType.LOSE, target, NOW, correlation_id="corr-5")
    new_target = GoalTarget(target_value=80.0, target_date=date(2026, 12, 1), now=NOW)
    event = profile.update_goal(GoalType.GAIN, new_target, NOW, correlation_id="corr-6")
    assert event.event_type == "GoalUpdated"
    assert event.payload["previous_goal_type"] == "LOSE"
    assert profile.goal_type == GoalType.GAIN


def test_update_goal_on_profile_with_no_goal_raises():
    profile = _create_profile()
    empty_target = GoalTarget()
    with pytest.raises(NoExistingGoalError):
        profile.update_goal(GoalType.MAINTAIN, empty_target, NOW, correlation_id="corr-6")


def test_full_replay_yields_latest_weight_and_goal():
    profile, created = Profile.create(USER_ID, correlation_id="corr-1")
    consent = profile.grant_consent(NOW, correlation_id="corr-2")
    first_weight = profile.record_weight(WeightKg(70.0), NOW, correlation_id="corr-3")
    second_weight = profile.record_weight(WeightKg(68.0), NOW, correlation_id="corr-4")
    target = GoalTarget(target_value=65.0, target_date=date(2026, 12, 1), now=NOW)
    goal_set = profile.set_goal(GoalType.LOSE, target, NOW, correlation_id="corr-5")

    rebuilt = Profile.rebuild([created, consent, first_weight, second_weight, goal_set])

    assert rebuilt.weight_kg == 68.0
    assert rebuilt.goal_type == GoalType.LOSE
    assert rebuilt.goal_target_value == 65.0
    assert rebuilt.goal_target_date == date(2026, 12, 1)
