"""build_exercise_logged_event tests -- payload shape and the structural
"label is never folded into exercise_type" guard (test-plan section 1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from domain.entities.exercise_entry import ExerciseEntry
from domain.events.exercise_logged import EVENT_TYPE, EVENT_VERSION, build_exercise_logged_event
from domain.value_objects.calories_burned import CaloriesBurned
from domain.value_objects.duration_minutes import DurationMinutes
from domain.value_objects.exercise_type import ExerciseType


def _make_entry(**overrides: object) -> ExerciseEntry:
    now = datetime.now(timezone.utc)
    defaults: dict[str, object] = dict(
        entry_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exercise_type=ExerciseType.OTHER,
        duration=DurationMinutes(20),
        calories_burned=CaloriesBurned(120.0),
        occurred_at=now,
        created_at=now,
        updated_at=now,
        label="rock climbing",
        deleted_at=None,
    )
    defaults.update(overrides)
    return ExerciseEntry(**defaults)  # type: ignore[arg-type]


def test_payload_matches_entry_fields() -> None:
    entry = _make_entry()
    event = build_exercise_logged_event(entry=entry, correlation_id="corr-1")

    assert event.event_type == EVENT_TYPE
    assert event.version == EVENT_VERSION
    assert event.aggregate_id == str(entry.entry_id)
    assert event.metadata.correlation_id == "corr-1"
    assert event.metadata.user_id == str(entry.user_id)
    assert event.payload["entry_id"] == str(entry.entry_id)
    assert event.payload["duration_minutes"] == 20
    assert event.payload["calories_burned_kcal"] == 120.0
    assert event.payload["occurred_at"] == entry.occurred_at.isoformat()


def test_label_is_a_secondary_field_never_folded_into_exercise_type() -> None:
    entry = _make_entry(exercise_type=ExerciseType.OTHER, label="rock climbing")
    event = build_exercise_logged_event(entry=entry, correlation_id="corr-2")

    # The aggregable field is still the closed enum value, not the label.
    assert event.payload["exercise_type"] == "other"
    # The label is present, but as its own, clearly-secondary field.
    assert event.payload["label"] == "rock climbing"
    assert "other" not in {event.payload["label"]}
