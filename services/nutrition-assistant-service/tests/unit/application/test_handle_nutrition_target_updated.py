from __future__ import annotations

import uuid

import pytest

from application.commands.handle_nutrition_target_updated import (
    HandleNutritionTargetUpdatedCommand,
    HandleNutritionTargetUpdatedHandler,
)
from tests.fixtures.fakes import FakeNutritionHistoryRepository, FakeProcessedEventsRepository


@pytest.fixture
def handler():
    processed = FakeProcessedEventsRepository()
    nutrition_history = FakeNutritionHistoryRepository()
    return HandleNutritionTargetUpdatedHandler(processed, nutrition_history), nutrition_history


async def test_valid_event_upserts_target(handler) -> None:
    h, nutrition_history = handler
    await h.handle(
        HandleNutritionTargetUpdatedCommand(
            event_id=uuid.uuid4(), user_id=uuid.uuid4(), summary="target: 2000 kcal"
        )
    )
    assert len(nutrition_history.upsert_target_calls) == 1


async def test_idempotent_replay(handler) -> None:
    h, nutrition_history = handler
    event_id = uuid.uuid4()
    command = HandleNutritionTargetUpdatedCommand(
        event_id=event_id, user_id=uuid.uuid4(), summary="target: 2000 kcal"
    )
    await h.handle(command)
    await h.handle(command)
    assert len(nutrition_history.upsert_target_calls) == 1
