"""ExerciseEntry entity tests -- `corrected`/`soft_deleted` behavior not
already covered indirectly via the application-layer handler tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from domain.entities.exercise_entry import ExerciseEntry
from domain.value_objects.calories_burned import CaloriesBurned
from domain.value_objects.duration_minutes import DurationMinutes
from domain.value_objects.exercise_type import ExerciseType


def _make_entry(**overrides: object) -> ExerciseEntry:
    now = datetime.now(timezone.utc)
    defaults: dict[str, object] = dict(
        entry_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type=ExerciseType.RUNNING,
        duration=DurationMinutes(30),
        calories_burned=CaloriesBurned(250.0),
        occurred_at=now,
        created_at=now,
        updated_at=now,
        label=None,
        deleted_at=None,
    )
    defaults.update(overrides)
    return ExerciseEntry(**defaults)  # type: ignore[arg-type]


def test_is_deleted_false_by_default() -> None:
    assert _make_entry().is_deleted is False


def test_corrected_only_changes_supplied_fields() -> None:
    entry = _make_entry()
    later = entry.updated_at + timedelta(minutes=1)
    corrected = entry.corrected(now=later, duration=DurationMinutes(45))

    assert int(corrected.duration) == 45
    assert corrected.exercise_type == entry.exercise_type
    assert corrected.calories_burned == entry.calories_burned
    assert corrected.occurred_at == entry.occurred_at
    assert corrected.updated_at == later
    assert corrected.entry_id == entry.entry_id


def test_corrected_clears_label_when_explicit_none_supplied() -> None:
    entry = _make_entry(label="a note")
    later = entry.updated_at + timedelta(minutes=1)
    corrected = entry.corrected(now=later, label=None)
    assert corrected.label is None


def test_corrected_leaves_label_unchanged_when_not_supplied() -> None:
    entry = _make_entry(label="a note")
    later = entry.updated_at + timedelta(minutes=1)
    corrected = entry.corrected(now=later, duration=DurationMinutes(10))
    assert corrected.label == "a note"


def test_soft_deleted_sets_deleted_at() -> None:
    entry = _make_entry()
    later = entry.updated_at + timedelta(minutes=1)
    deleted = entry.soft_deleted(now=later)
    assert deleted.is_deleted is True
    assert deleted.deleted_at == later


def test_soft_deleted_is_idempotent() -> None:
    entry = _make_entry()
    first_delete_time = entry.updated_at + timedelta(minutes=1)
    deleted_once = entry.soft_deleted(now=first_delete_time)

    second_delete_time = first_delete_time + timedelta(minutes=1)
    deleted_twice = deleted_once.soft_deleted(now=second_delete_time)

    assert deleted_twice.deleted_at == first_delete_time
    assert deleted_twice is deleted_once
