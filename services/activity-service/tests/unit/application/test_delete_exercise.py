"""DeleteExerciseHandler unit tests (test-plan section 1)."""

from __future__ import annotations

import uuid

import pytest

from application.commands.delete_exercise import DeleteExerciseCommand, DeleteExerciseHandler
from application.errors import ExerciseEntryNotFoundError
from tests.fixtures.factories import FakeExerciseRepository, make_exercise_entry


@pytest.fixture
def repository() -> FakeExerciseRepository:
    return FakeExerciseRepository()


async def test_existing_entry_is_soft_deleted_never_hard_deleted(
    repository: FakeExerciseRepository,
) -> None:
    user_id = uuid.uuid4()
    entry = make_exercise_entry(user_id=user_id)
    repository.entries[entry.entry_id] = entry
    handler = DeleteExerciseHandler(repository=repository)

    await handler.handle(DeleteExerciseCommand(entry_id=entry.entry_id, user_id=user_id))

    persisted = repository.entries[entry.entry_id]
    assert persisted.is_deleted is True
    assert persisted.deleted_at is not None
    assert len(repository.update_calls) == 1
    assert repository.delete_calls == []


async def test_nonexistent_entry_raises() -> None:
    repository = FakeExerciseRepository()
    handler = DeleteExerciseHandler(repository=repository)

    with pytest.raises(ExerciseEntryNotFoundError):
        await handler.handle(DeleteExerciseCommand(entry_id=uuid.uuid4(), user_id=uuid.uuid4()))


async def test_already_deleted_entry_is_idempotent_no_op(
    repository: FakeExerciseRepository,
) -> None:
    import datetime as dt

    user_id = uuid.uuid4()
    entry = make_exercise_entry(user_id=user_id, deleted_at=dt.datetime.now(dt.timezone.utc))
    repository.entries[entry.entry_id] = entry
    handler = DeleteExerciseHandler(repository=repository)

    await handler.handle(DeleteExerciseCommand(entry_id=entry.entry_id, user_id=user_id))
    await handler.handle(DeleteExerciseCommand(entry_id=entry.entry_id, user_id=user_id))

    assert repository.update_calls == []
    assert repository.delete_calls == []
