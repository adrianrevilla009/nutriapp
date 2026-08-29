"""LogExerciseHandler unit tests (test-plan section 1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from application.commands.log_exercise import LogExerciseCommand, LogExerciseHandler
from tests.fixtures.factories import FakeExerciseRepository, FakeOutboxRepository


@pytest.fixture
def repository() -> FakeExerciseRepository:
    return FakeExerciseRepository()


@pytest.fixture
def outbox() -> FakeOutboxRepository:
    return FakeOutboxRepository()


async def test_valid_command_persists_entry_and_publishes_event(
    repository: FakeExerciseRepository, outbox: FakeOutboxRepository
) -> None:
    handler = LogExerciseHandler(repository=repository, outbox_repository=outbox)
    user_id = uuid.uuid4()
    occurred_at = datetime(2026, 8, 20, 7, 0, tzinfo=timezone.utc)

    result = await handler.handle(
        LogExerciseCommand(
            user_id=user_id,
            exercise_type="running",
            duration_minutes=30,
            calories_burned_kcal=250.0,
            occurred_at=occurred_at,
            correlation_id="corr-1",
        )
    )

    assert result.entry.entry_id in repository.entries
    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.payload["exercise_type"] == "running"
    assert event.payload["duration_minutes"] == 30
    assert event.payload["calories_burned_kcal"] == 250.0
    assert event.payload["occurred_at"] == occurred_at.isoformat()
    assert event.metadata.user_id == str(user_id)


async def test_other_type_with_label_keeps_label_out_of_aggregable_fields(
    repository: FakeExerciseRepository, outbox: FakeOutboxRepository
) -> None:
    handler = LogExerciseHandler(repository=repository, outbox_repository=outbox)

    result = await handler.handle(
        LogExerciseCommand(
            user_id=uuid.uuid4(),
            exercise_type="other",
            duration_minutes=15,
            calories_burned_kcal=80.0,
            occurred_at=datetime.now(timezone.utc),
            correlation_id="corr-2",
            label="frisbee",
        )
    )

    assert result.entry.label == "frisbee"
    event = outbox.enqueued[0]
    # exercise_type stays the enum value -- the label never overrides it.
    assert event.payload["exercise_type"] == "other"
    assert event.payload["label"] == "frisbee"
