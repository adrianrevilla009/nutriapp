from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from application.commands.handle_food_entry_logged import (
    HandleFoodEntryLoggedCommand,
    HandleFoodEntryLoggedHandler,
)
from tests.fixtures.fakes import FakeDiaryHistoryRepository, FakeProcessedEventsRepository


@pytest.fixture
def handler():
    processed = FakeProcessedEventsRepository()
    diary_history = FakeDiaryHistoryRepository()
    return HandleFoodEntryLoggedHandler(processed, diary_history), processed, diary_history


async def test_valid_event_upserts_entry(handler) -> None:
    h, processed, diary_history = handler
    entry_id, user_id = uuid.uuid4(), uuid.uuid4()
    command = HandleFoodEntryLoggedCommand(
        event_id=uuid.uuid4(),
        entry_id=entry_id,
        user_id=user_id,
        summary="200g chicken breast",
        occurred_at=datetime.now(UTC),
    )
    await h.handle(command)
    assert entry_id in diary_history.food_entries
    assert diary_history.food_entries[entry_id].summary == "200g chicken breast"


async def test_idempotent_replay_is_a_no_op(handler) -> None:
    h, processed, diary_history = handler
    event_id = uuid.uuid4()
    command = HandleFoodEntryLoggedCommand(
        event_id=event_id,
        entry_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        summary="200g chicken breast",
        occurred_at=datetime.now(UTC),
    )
    await h.handle(command)
    await h.handle(command)
    assert len(diary_history.upsert_food_entry_calls) == 1


async def test_incremental_write_touches_only_the_affected_entry(handler) -> None:
    """Direct test of the agent doc's core requirement: handling one event
    never triggers a full-history fetch/rewrite for the user."""
    h, processed, diary_history = handler
    command = HandleFoodEntryLoggedCommand(
        event_id=uuid.uuid4(),
        entry_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        summary="200g chicken breast",
        occurred_at=datetime.now(UTC),
    )
    await h.handle(command)
    assert len(diary_history.upsert_food_entry_calls) == 1
    assert diary_history.upsert_food_entry_calls[0][0] == command.entry_id
    # No "fetch/rewrite everything for this user" call exists on the fake
    # at all -- the port itself has no such method, which is the
    # structural guarantee this test documents.
    assert diary_history.recent_for_user_calls == []
