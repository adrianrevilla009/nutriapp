from __future__ import annotations

import pytest

from domain.services.recomputation_policy import (
    UnrecognizedTriggerEventError,
    target_recompute_reason_for,
    total_recompute_reason_for,
)


@pytest.mark.parametrize(
    "event_type,expected_reason",
    [
        ("FoodEntryLogged", "food_entry_logged"),
        ("FoodEntryCorrected", "food_entry_corrected"),
        ("FoodEntryDeleted", "food_entry_deleted"),
    ],
)
def test_total_recompute_reason_mapping(event_type, expected_reason):
    assert total_recompute_reason_for(event_type) == expected_reason


@pytest.mark.parametrize(
    "event_type,expected_reason",
    [
        ("WeightRecorded", "weight_recorded"),
        ("BodyMetricRecorded", "body_metric_recorded"),
        ("GoalSet", "goal_set"),
        ("GoalUpdated", "goal_updated"),
    ],
)
def test_target_recompute_reason_mapping(event_type, expected_reason):
    assert target_recompute_reason_for(event_type) == expected_reason


def test_unrecognized_trigger_raises_for_total():
    with pytest.raises(UnrecognizedTriggerEventError):
        total_recompute_reason_for("SomethingElse")


def test_unrecognized_trigger_raises_for_target():
    with pytest.raises(UnrecognizedTriggerEventError):
        target_recompute_reason_for("SomethingElse")
