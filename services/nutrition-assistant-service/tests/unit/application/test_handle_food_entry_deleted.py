from __future__ import annotations

import uuid

import pytest

from application.commands.handle_food_entry_deleted import (
    HandleFoodEntryDeletedCommand,
    HandleFoodEntryDeletedHandler,
)
from tests.fixtures.fakes import FakeDiaryHistoryRepository, FakeProcessedEventsRepository


@pytest.fixture
def handler():
    processed = FakeProcessedEventsRepository()
    diary_history = FakeDiaryHistoryRepository()
    return HandleFoodEntryDeletedHandler(processed, diary_history), diary_history


async def test_removes_entry(handler) -> None:
    h, diary_history = handler
    entry_id = uuid.uuid4()
    diary_history.food_entries[entry_id] = object()  # type: ignore[assignment]
    await h.handle(HandleFoodEntryDeletedCommand(event_id=uuid.uuid4(), entry_id=entry_id))
    assert entry_id not in diary_history.food_entries


async def test_idempotent_replay_never_errors_on_missing_row(handler) -> None:
    h, diary_history = handler
    event_id = uuid.uuid4()
    command = HandleFoodEntryDeletedCommand(event_id=event_id, entry_id=uuid.uuid4())
    await h.handle(command)
    await h.handle(command)  # must not raise
