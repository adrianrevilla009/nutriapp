from __future__ import annotations

import uuid

import pytest

from application.commands.handle_water_intake_removed import (
    HandleWaterIntakeRemovedCommand,
    HandleWaterIntakeRemovedHandler,
)
from tests.fixtures.fakes import FakeDiaryHistoryRepository, FakeProcessedEventsRepository


@pytest.fixture
def handler():
    processed = FakeProcessedEventsRepository()
    diary_history = FakeDiaryHistoryRepository()
    return HandleWaterIntakeRemovedHandler(processed, diary_history), diary_history


async def test_duplicate_delivery_does_not_double_remove(handler) -> None:
    h, diary_history = handler
    intake_id = uuid.uuid4()
    diary_history.water_intakes[intake_id] = object()  # type: ignore[assignment]
    event_id = uuid.uuid4()
    command = HandleWaterIntakeRemovedCommand(event_id=event_id, intake_id=intake_id)

    await h.handle(command)
    assert intake_id not in diary_history.water_intakes

    await h.handle(command)  # duplicate delivery -- must not raise, no double-remove effect
    assert intake_id not in diary_history.water_intakes
