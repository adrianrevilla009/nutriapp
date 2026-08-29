"""ListExercisesForDateQuery/Handler -- implements implementation plan
section 1, acceptance criterion 4: list the authenticated user's exercise
entries for a given date. User-scoping and soft-delete exclusion are
enforced at the repository query level, never just trusted from the
caller (test-plan section 1)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from domain.entities.exercise_entry import ExerciseEntry
from domain.ports.exercise_repository_port import ExerciseRepositoryPort


@dataclass(frozen=True, slots=True)
class ListExercisesForDateQuery:
    user_id: uuid.UUID
    occurred_on: date


class ListExercisesForDateHandler:
    def __init__(self, repository: ExerciseRepositoryPort) -> None:
        self._repository = repository

    async def handle(self, query: ListExercisesForDateQuery) -> list[ExerciseEntry]:
        return await self._repository.list_for_user_and_date(query.user_id, query.occurred_on)
