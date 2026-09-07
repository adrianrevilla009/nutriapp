from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from application.commands.handle_water_intake_logged import (
    HandleWaterIntakeLoggedCommand,
    HandleWaterIntakeLoggedHandler,
)
from tests.fixtures.fakes import FakeDiaryHistoryRepository, FakeProcessedEventsRepository


@pytest.fixture
def handler():
    processed = FakeProcessedEventsRepository()
    diary_history = FakeDiaryHistoryRepository()
    return HandleWaterIntakeLoggedHandler(processed, diary_history), diary_history


async def test_valid_event_upserts(handler) -> None:
    h, diary_history = handler
    intake_id, user_id = uuid.uuid4(), uuid.uuid4()
    await h.handle(
        HandleWaterIntakeLoggedCommand(
            event_id=uuid.uuid4(),
            intake_id=intake_id,
            user_id=user_id,
            summary="500ml water",
            occurred_at=datetime.now(UTC),
        )
    )
    assert intake_id in diary_history.water_intakes


async def test_idempotent_replay(handler) -> None:
    h, diary_history = handler
    event_id = uuid.uuid4()
    command = HandleWaterIntakeLoggedCommand(
        event_id=event_id,
        intake_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        summary="500ml water",
        occurred_at=datetime.now(UTC),
    )
    await h.handle(command)
    await h.handle(command)
    assert len(diary_history.upsert_water_intake_calls) == 1
