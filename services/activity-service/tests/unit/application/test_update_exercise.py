"""UpdateExerciseHandler unit tests (test-plan section 1)."""

from __future__ import annotations

import uuid

import pytest

from application.commands.update_exercise import UpdateExerciseCommand, UpdateExerciseHandler
from application.errors import ExerciseEntryAlreadyDeletedError, ExerciseEntryNotFoundError
from tests.fixtures.factories import (
    FakeExerciseRepository,
    FakeOutboxRepository,
    make_exercise_entry,
)


@pytest.fixture
def repository() -> FakeExerciseRepository:
    return FakeExerciseRepository()


@pytest.fixture
def outbox() -> FakeOutboxRepository:
    return FakeOutboxRepository()


async def test_valid_update_is_persisted_and_published_exactly_once(
    repository: FakeExerciseRepository, outbox: FakeOutboxRepository
) -> None:
    user_id = uuid.uuid4()
    entry = make_exercise_entry(user_id=user_id, duration_minutes=30)
    repository.entries[entry.entry_id] = entry
    handler = UpdateExerciseHandler(repository=repository, outbox_repository=outbox)

    result = await handler.handle(
        UpdateExerciseCommand(
            entry_id=entry.entry_id,
            user_id=user_id,
            correlation_id="corr-1",
            duration_minutes=45,
        )
    )

    assert int(result.entry.duration) == 45
    read_back = repository.entries[entry.entry_id]
    assert int(read_back.duration) == 45
    assert len(outbox.enqueued) == 1


async def test_nonexistent_entry_raises_and_never_writes(
    repository: FakeExerciseRepository, outbox: FakeOutboxRepository
) -> None:
    handler = UpdateExerciseHandler(repository=repository, outbox_repository=outbox)

    with pytest.raises(ExerciseEntryNotFoundError):
        await handler.handle(
            UpdateExerciseCommand(
                entry_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                correlation_id="corr-2",
                duration_minutes=45,
            )
        )

    assert repository.update_calls == []
    assert outbox.enqueued == []


async def test_soft_deleted_entry_rejects_update(
    repository: FakeExerciseRepository, outbox: FakeOutboxRepository
) -> None:
    user_id = uuid.uuid4()
    import datetime as dt

    entry = make_exercise_entry(user_id=user_id, deleted_at=dt.datetime.now(dt.timezone.utc))
    repository.entries[entry.entry_id] = entry
    handler = UpdateExerciseHandler(repository=repository, outbox_repository=outbox)

    with pytest.raises(ExerciseEntryAlreadyDeletedError):
        await handler.handle(
            UpdateExerciseCommand(
                entry_id=entry.entry_id,
                user_id=user_id,
                correlation_id="corr-3",
                duration_minutes=10,
            )
        )

    assert repository.update_calls == []
    assert outbox.enqueued == []
