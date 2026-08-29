"""ExerciseEntry -- a manually logged exercise entry. Conventional
persistence, not event-sourced (ADR-0002, implementation plan section 2):
this entity is the `exercise_entries` table's in-memory shape, one row per
entry, corrected/soft-deleted in place -- never a fold over an event
stream. `ExerciseLogged` is derived as a side effect of a successful
log/update, published via the Outbox pattern by the application layer;
this module has zero knowledge of the outbox/messaging.

Soft delete only (`deleted_at`), matching `diary-service`'s "never a
destructive row delete" convention even though this service isn't
event-sourced, for the same audit-friendliness reason (implementation
plan section 1, acceptance criterion 3).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import datetime

from domain.value_objects.calories_burned import CaloriesBurned
from domain.value_objects.duration_minutes import DurationMinutes
from domain.value_objects.exercise_type import ExerciseType


class _Unset:
    """Sentinel type distinguishing "field not supplied" from an explicit
    `None` for `ExerciseEntry.corrected`'s `label` parameter."""


_UNSET = _Unset()


@dataclass(frozen=True, slots=True)
class ExerciseEntry:
    entry_id: uuid.UUID
    user_id: uuid.UUID
    exercise_type: ExerciseType
    duration: DurationMinutes
    calories_burned: CaloriesBurned
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime
    # Free-text label, meaningful only for `ExerciseType.OTHER` -- display
    # only, deliberately never part of `ExerciseLogged`'s aggregable
    # fields (test-plan section 1: "guards against the free-text label
    # silently becoming a de facto second taxonomy").
    label: str | None = None
    deleted_at: datetime | None = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def corrected(
        self,
        *,
        now: datetime,
        exercise_type: ExerciseType | None = None,
        duration: DurationMinutes | None = None,
        calories_burned: CaloriesBurned | None = None,
        occurred_at: datetime | None = None,
        label: str | None | _Unset = _UNSET,
    ) -> ExerciseEntry:
        """Returns a corrected copy -- conventional field update (PATCH
        semantics: only fields explicitly supplied are changed), never a
        destructive rewrite of history (implementation plan section 1,
        acceptance criterion 2). `label` uses a sentinel default so an
        explicit `label=None` (clearing it) is distinguishable from "not
        supplied"."""
        resolved_label: str | None = self.label if isinstance(label, _Unset) else label
        return replace(
            self,
            exercise_type=exercise_type if exercise_type is not None else self.exercise_type,
            duration=duration if duration is not None else self.duration,
            calories_burned=(
                calories_burned if calories_burned is not None else self.calories_burned
            ),
            occurred_at=occurred_at if occurred_at is not None else self.occurred_at,
            label=resolved_label,
            updated_at=now,
        )

    def soft_deleted(self, *, now: datetime) -> ExerciseEntry:
        """Idempotent: soft-deleting an already-deleted entry returns an
        equivalent entry with the same original `deleted_at`, never a
        second timestamp (test-plan section 1: "Already-deleted entry ->
        idempotent no-op")."""
        if self.is_deleted:
            return self
        return replace(self, deleted_at=now, updated_at=now)
