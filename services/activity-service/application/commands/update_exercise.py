"""UpdateExerciseCommand/Handler -- implements implementation plan section
1, acceptance criterion 2: correct a previously logged entry (a
straightforward field update, not event-sourced). Republishes
`ExerciseLogged` reflecting the corrected figures so downstream TDEE
consumers see the current calorie-burn value, not a stale one -- exactly
one publish per invocation (test-plan section 1).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from application.errors import ExerciseEntryAlreadyDeletedError, ExerciseEntryNotFoundError
from domain.entities.exercise_entry import ExerciseEntry
from domain.events.exercise_logged import build_exercise_logged_event
from domain.ports.exercise_repository_port import ExerciseRepositoryPort
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.value_objects.calories_burned import CaloriesBurned
from domain.value_objects.duration_minutes import DurationMinutes
from domain.value_objects.exercise_type import ExerciseType

# Sentinel distinguishing "label not supplied" (leave unchanged) from an
# explicit `label=None` (clear it) at the command boundary too -- mirrors
# `domain.entities.exercise_entry._UNSET`'s rationale, kept as a separate
# instance so the application layer doesn't reach into the domain
# module's "private" sentinel.
_LABEL_NOT_SUPPLIED = object()


@dataclass(frozen=True, slots=True)
class UpdateExerciseCommand:
    entry_id: uuid.UUID
    user_id: uuid.UUID
    correlation_id: str
    exercise_type: str | None = None
    duration_minutes: int | None = None
    calories_burned_kcal: float | None = None
    occurred_at: datetime | None = None
    label: str | None = _LABEL_NOT_SUPPLIED  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class UpdateExerciseResult:
    entry: ExerciseEntry


class UpdateExerciseHandler:
    def __init__(
        self,
        repository: ExerciseRepositoryPort,
        outbox_repository: OutboxRepositoryPort,
    ) -> None:
        self._repository = repository
        self._outbox_repository = outbox_repository

    async def handle(self, command: UpdateExerciseCommand) -> UpdateExerciseResult:
        existing = await self._repository.get_by_id_and_user(command.entry_id, command.user_id)
        if existing is None:
            raise ExerciseEntryNotFoundError(f"No exercise entry {command.entry_id} found.")
        if existing.is_deleted:
            raise ExerciseEntryAlreadyDeletedError(
                f"Exercise entry {command.entry_id} has been deleted and can no longer be corrected."
            )

        now = datetime.now(timezone.utc)
        corrected = existing.corrected(
            now=now,
            exercise_type=(
                ExerciseType(command.exercise_type) if command.exercise_type is not None else None
            ),
            duration=(
                DurationMinutes(command.duration_minutes)
                if command.duration_minutes is not None
                else None
            ),
            calories_burned=(
                CaloriesBurned(command.calories_burned_kcal)
                if command.calories_burned_kcal is not None
                else None
            ),
            occurred_at=command.occurred_at,
            label=(existing.label if command.label is _LABEL_NOT_SUPPLIED else command.label),
        )
        await self._repository.update(corrected)
        event = build_exercise_logged_event(entry=corrected, correlation_id=command.correlation_id)
        await self._outbox_repository.enqueue(event)
        return UpdateExerciseResult(entry=corrected)
