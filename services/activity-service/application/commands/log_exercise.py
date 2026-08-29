"""LogExerciseCommand/Handler -- implements implementation plan section 1,
acceptance criterion 1: log a manual exercise entry, publishing
`ExerciseLogged` (v1) via the Outbox in the same transaction as the write.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from domain.entities.exercise_entry import ExerciseEntry
from domain.events.exercise_logged import build_exercise_logged_event
from domain.ports.exercise_repository_port import ExerciseRepositoryPort
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.value_objects.calories_burned import CaloriesBurned
from domain.value_objects.duration_minutes import DurationMinutes
from domain.value_objects.exercise_type import ExerciseType


@dataclass(frozen=True, slots=True)
class LogExerciseCommand:
    user_id: uuid.UUID
    exercise_type: str
    duration_minutes: int
    calories_burned_kcal: float
    occurred_at: datetime
    correlation_id: str
    label: str | None = None


@dataclass(frozen=True, slots=True)
class LogExerciseResult:
    entry: ExerciseEntry


class LogExerciseHandler:
    def __init__(
        self,
        repository: ExerciseRepositoryPort,
        outbox_repository: OutboxRepositoryPort,
    ) -> None:
        self._repository = repository
        self._outbox_repository = outbox_repository

    async def handle(self, command: LogExerciseCommand) -> LogExerciseResult:
        now = datetime.now(timezone.utc)
        entry = ExerciseEntry(
            entry_id=uuid.uuid4(),
            user_id=command.user_id,
            exercise_type=ExerciseType(command.exercise_type),
            duration=DurationMinutes(command.duration_minutes),
            calories_burned=CaloriesBurned(command.calories_burned_kcal),
            occurred_at=command.occurred_at,
            created_at=now,
            updated_at=now,
            label=command.label,
        )
        await self._repository.add(entry)
        event = build_exercise_logged_event(entry=entry, correlation_id=command.correlation_id)
        await self._outbox_repository.enqueue(event)
        return LogExerciseResult(entry=entry)
