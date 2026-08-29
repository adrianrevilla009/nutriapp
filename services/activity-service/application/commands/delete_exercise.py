"""DeleteExerciseCommand/Handler -- implements implementation plan section
1, acceptance criterion 3: soft-delete a logged entry. Idempotent: a
second delete of an already-deleted entry is a no-op (no repository
write, no event) -- test-plan section 1/3.

No domain event is published for a delete in this plan's scope --
implementation plan section 5 documents only `ExerciseLogged` as this
service's published event; there is no "ExerciseDeleted" event to
publish. Downstream consumers observe the disappearance only via this
service's own list/read APIs, same as `diary-service`'s soft-delete
convention this mirrors.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from application.errors import ExerciseEntryNotFoundError
from domain.ports.exercise_repository_port import ExerciseRepositoryPort


@dataclass(frozen=True, slots=True)
class DeleteExerciseCommand:
    entry_id: uuid.UUID
    user_id: uuid.UUID


class DeleteExerciseHandler:
    def __init__(self, repository: ExerciseRepositoryPort) -> None:
        self._repository = repository

    async def handle(self, command: DeleteExerciseCommand) -> None:
        existing = await self._repository.get_by_id_and_user(command.entry_id, command.user_id)
        if existing is None:
            raise ExerciseEntryNotFoundError(f"No exercise entry {command.entry_id} found.")
        if existing.is_deleted:
            # Idempotent no-op -- never a second write, never a second
            # (nonexistent) event.
            return
        now = datetime.now(timezone.utc)
        deleted = existing.soft_deleted(now=now)
        await self._repository.update(deleted)
