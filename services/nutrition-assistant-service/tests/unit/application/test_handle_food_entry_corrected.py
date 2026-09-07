from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from application.commands.handle_food_entry_corrected import (
    HandleFoodEntryCorrectedCommand,
    HandleFoodEntryCorrectedHandler,
)
from tests.fixtures.fakes import FakeDiaryHistoryRepository, FakeProcessedEventsRepository


@pytest.fixture
def handler():
    processed = FakeProcessedEventsRepository()
    diary_history = FakeDiaryHistoryRepository()
    return HandleFoodEntryCorrectedHandler(processed, diary_history), diary_history


async def test_valid_event_replaces_summary(handler) -> None:
    h, diary_history = handler
    entry_id, user_id = uuid.uuid4(), uuid.uuid4()
    command = HandleFoodEntryCorrectedCommand(
        event_id=uuid.uuid4(),
        entry_id=entry_id,
        user_id=user_id,
        summary="corrected: 150g chicken breast",
        occurred_at=datetime.now(UTC),
    )
    await h.handle(command)
    assert diary_history.food_entries[entry_id].summary == "corrected: 150g chicken breast"


async def test_idempotent_replay(handler) -> None:
    h, diary_history = handler
    event_id = uuid.uuid4()
    command = HandleFoodEntryCorrectedCommand(
        event_id=event_id,
        entry_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        summary="x",
        occurred_at=datetime.now(UTC),
    )
    await h.handle(command)
    await h.handle(command)
    assert len(diary_history.upsert_food_entry_calls) == 1
