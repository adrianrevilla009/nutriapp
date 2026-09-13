"""WearableSyncResult -- test-plan addendum (2026-09-11) section 1."""

from __future__ import annotations

from datetime import datetime, timezone

from domain.ports.wearable_provider_port import WearableSyncResult
from domain.value_objects.calories_burned import CaloriesBurned
from domain.value_objects.duration_minutes import DurationMinutes
from domain.value_objects.exercise_type import ExerciseType


def test_valid_construction_with_mapped_exercise_type():
    result = WearableSyncResult(
        provider_activity_id="12345",
        exercise_type=ExerciseType.RUNNING,
        duration=DurationMinutes(30),
        calories_burned=CaloriesBurned(312),
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert result.exercise_type is ExerciseType.RUNNING
    assert int(result.duration) == 30
    assert float(result.calories_burned) == 312
    assert result.label is None


def test_other_exercise_type_carries_provider_label():
    result = WearableSyncResult(
        provider_activity_id="99999",
        exercise_type=ExerciseType.OTHER,
        duration=DurationMinutes(15),
        calories_burned=CaloriesBurned(80),
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        label="Pilates",
    )
    assert result.exercise_type is ExerciseType.OTHER
    assert result.label == "Pilates"


def test_calories_burned_carried_through_without_arithmetic():
    # No precision is invented -- constructing directly from a provider's
    # raw reported integer kcal figure must round-trip exactly.
    raw_provider_calories = 247
    result = WearableSyncResult(
        provider_activity_id="1",
        exercise_type=ExerciseType.CYCLING,
        duration=DurationMinutes(45),
        calories_burned=CaloriesBurned(raw_provider_calories),
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert float(result.calories_burned) == float(raw_provider_calories)
