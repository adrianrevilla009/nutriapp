"""Fake in-memory ports for unit tests (testing-strategy SKILL.md) --
no I/O, exercise handler logic in isolation. Also a small builder helper
for constructing valid `ExerciseEntry` instances in tests without
repeating every field."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from domain.entities.exercise_entry import ExerciseEntry
from domain.events.base import DomainEvent
from domain.value_objects.calories_burned import CaloriesBurned
from domain.value_objects.duration_minutes import DurationMinutes
from domain.value_objects.exercise_type import ExerciseType


def make_exercise_entry(
    *,
    entry_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    exercise_type: ExerciseType = ExerciseType.RUNNING,
    duration_minutes: int = 30,
    calories_burned_kcal: float = 250.0,
    occurred_at: datetime | None = None,
    label: str | None = None,
    deleted_at: datetime | None = None,
) -> ExerciseEntry:
    now = datetime.now(timezone.utc)
    return ExerciseEntry(
        entry_id=entry_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        exercise_type=exercise_type,
        duration=DurationMinutes(duration_minutes),
        calories_burned=CaloriesBurned(calories_burned_kcal),
        occurred_at=occurred_at or now,
        created_at=now,
        updated_at=now,
        label=label,
        deleted_at=deleted_at,
    )


class FakeExerciseRepository:
    """Implements domain.ports.exercise_repository_port.ExerciseRepositoryPort.

    Deliberately exposes a `delete()` method distinct from `update()` even
    though the real port never defines one -- test-plan section 1's
    `DeleteExerciseHandler` case asserts this method is NEVER called,
    only the soft-delete/`update()` path, as a structural safety net
    against ever wiring a hard delete in by mistake.
    """

    def __init__(self) -> None:
        self.entries: dict[uuid.UUID, ExerciseEntry] = {}
        self.add_calls: list[ExerciseEntry] = []
        self.update_calls: list[ExerciseEntry] = []
        self.delete_calls: list[uuid.UUID] = []

    async def add(self, entry: ExerciseEntry) -> None:
        self.entries[entry.entry_id] = entry
        self.add_calls.append(entry)

    async def get_by_id_and_user(
        self, entry_id: uuid.UUID, user_id: uuid.UUID
    ) -> ExerciseEntry | None:
        entry = self.entries.get(entry_id)
        if entry is None or entry.user_id != user_id:
            return None
        return entry

    async def update(self, entry: ExerciseEntry) -> None:
        self.entries[entry.entry_id] = entry
        self.update_calls.append(entry)

    async def delete(self, entry_id: uuid.UUID) -> None:
        """Never called by any real handler -- see class docstring."""
        self.delete_calls.append(entry_id)
        del self.entries[entry_id]

    async def list_for_user_and_date(
        self, user_id: uuid.UUID, occurred_on: date
    ) -> list[ExerciseEntry]:
        matches = [
            e
            for e in self.entries.values()
            if e.user_id == user_id and e.deleted_at is None and e.occurred_at.date() == occurred_on
        ]
        return sorted(matches, key=lambda e: e.occurred_at)


class FakeOutboxRepository:
    """Implements domain.ports.outbox_repository_port.OutboxRepositoryPort."""

    def __init__(self) -> None:
        self.enqueued: list[DomainEvent] = []

    async def enqueue(self, event: DomainEvent) -> None:
        self.enqueued.append(event)

    async def fetch_unpublished(self, limit: int = 100) -> list[DomainEvent]:
        return list(self.enqueued[:limit])

    async def mark_published(self, event_id: uuid.UUID) -> None:
        return None
