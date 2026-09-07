from __future__ import annotations

import uuid
from datetime import date

import pytest

from application.commands.handle_nutrition_value_recomputed import (
    HandleNutritionValueRecomputedCommand,
    HandleNutritionValueRecomputedHandler,
)
from tests.fixtures.fakes import FakeNutritionHistoryRepository, FakeProcessedEventsRepository


@pytest.fixture
def handler():
    processed = FakeProcessedEventsRepository()
    nutrition_history = FakeNutritionHistoryRepository()
    return HandleNutritionValueRecomputedHandler(processed, nutrition_history), nutrition_history


async def test_valid_event_upserts(handler) -> None:
    h, nutrition_history = handler
    command = HandleNutritionValueRecomputedCommand(
        event_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        scope="day",
        reference_id="2026-09-07",
        on_date=date(2026, 9, 7),
        summary="1800 kcal, 120g protein",
    )
    await h.handle(command)
    assert len(nutrition_history.upsert_value_calls) == 1


async def test_idempotent_replay(handler) -> None:
    h, nutrition_history = handler
    event_id = uuid.uuid4()
    command = HandleNutritionValueRecomputedCommand(
        event_id=event_id,
        user_id=uuid.uuid4(),
        scope="day",
        reference_id="2026-09-07",
        on_date=date(2026, 9, 7),
        summary="x",
    )
    await h.handle(command)
    await h.handle(command)
    assert len(nutrition_history.upsert_value_calls) == 1


async def test_incremental_write_touches_only_affected_scope(handler) -> None:
    h, nutrition_history = handler
    command = HandleNutritionValueRecomputedCommand(
        event_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        scope="entry",
        reference_id="entry-123",
        on_date=None,
        summary="x",
    )
    await h.handle(command)
    assert nutrition_history.upsert_value_calls[0][2] == "entry-123"
    assert nutrition_history.recent_for_user_calls == []
