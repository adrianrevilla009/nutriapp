"""ExerciseRepositoryPort -- the write-model repository boundary for
`ExerciseEntry` (hexagonal-architecture SKILL.md). Deliberately exposes no
hard-delete method anywhere in this Protocol -- soft delete via
`soft_delete` is the only removal path (implementation plan section 1,
acceptance criterion 3)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Protocol

from domain.entities.exercise_entry import ExerciseEntry


class ExerciseRepositoryPort(Protocol):
    async def add(self, entry: ExerciseEntry) -> None: ...

    async def get_by_id_and_user(
        self, entry_id: uuid.UUID, user_id: uuid.UUID
    ) -> ExerciseEntry | None:
        """Returns the entry regardless of soft-delete state -- callers
        (e.g. `DeleteExerciseHandler`) need to distinguish "not found" from
        "already deleted" (test-plan section 1)."""
        ...

    async def update(self, entry: ExerciseEntry) -> None:
        """Persists a corrected or soft-deleted `ExerciseEntry` (same
        method for both -- a soft delete is just a field update, per
        `ExerciseEntry.soft_deleted`)."""
        ...

    async def list_for_user_and_date(
        self, user_id: uuid.UUID, occurred_on: date
    ) -> list[ExerciseEntry]:
        """Returns non-deleted entries for `user_id` whose `occurred_at`
        falls on `occurred_on` (UTC calendar day), ordered by
        `occurred_at` ascending. Never returns another user's entries or
        a soft-deleted entry."""
        ...
