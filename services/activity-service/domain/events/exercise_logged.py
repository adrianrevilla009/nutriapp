"""ExerciseLogged (v1) -- see docs/events-catalog.md and implementation
plan section 5. Published via the Outbox after every successful create
AND after every successful correction (implementation plan section 1,
acceptance criteria 1-2) -- there is no separate "ExerciseUpdated" event
in this plan's scope, since downstream TDEE consumers need the entry's
*current* calorie figure, not a diff. Never published on delete
(implementation plan section 1's acceptance criteria do not document a
delete-time event; deleting is a pure state change, no Outbox write).

The free-text `label` field (meaningful only for `ExerciseType.OTHER`) is
carried as a clearly-secondary payload field, never folded into
`exercise_type` itself -- guards against it silently becoming a de facto
second taxonomy (test-plan section 1).
"""

from __future__ import annotations

from domain.entities.exercise_entry import ExerciseEntry
from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "ExerciseLogged"
EVENT_VERSION = 1


def build_exercise_logged_event(
    *,
    entry: ExerciseEntry,
    correlation_id: str,
    causation_id: str | None = None,
) -> DomainEvent:
    payload = {
        "entry_id": str(entry.entry_id),
        "exercise_type": entry.exercise_type.value,
        "duration_minutes": int(entry.duration),
        "calories_burned_kcal": float(entry.calories_burned),
        "occurred_at": entry.occurred_at.isoformat(),
        "label": entry.label,
    }
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(entry.entry_id),
        payload=payload,
        metadata=EventMetadata(
            correlation_id=correlation_id,
            user_id=str(entry.user_id),
            causation_id=causation_id,
        ),
        # The envelope's own `occurred_at` records when this fact was
        # published (this write), distinct from the domain field
        # `ExerciseEntry.occurred_at` (when the user says the exercise
        # itself took place) -- deliberately reuses `entry.updated_at`
        # (write time), not the user-supplied `occurred_at`, to avoid the
        # two same-named concepts colliding.
        occurred_at=entry.updated_at,
    )
