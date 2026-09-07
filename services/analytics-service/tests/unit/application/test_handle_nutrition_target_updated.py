from __future__ import annotations

import uuid

from application.commands.handle_nutrition_target_updated import (
    HandleNutritionTargetUpdatedCommand,
    HandleNutritionTargetUpdatedHandler,
)
from tests.fixtures.factories import (
    FakeMicronutrientWindowRepository,
    FakeProcessedNutritionCalculationEventsRepository,
)


async def test_valid_event_updates_current_target_for_tracked_nutrients():
    processed = FakeProcessedNutritionCalculationEventsRepository()
    window = FakeMicronutrientWindowRepository()
    user_id = uuid.uuid4()
    handler = HandleNutritionTargetUpdatedHandler(processed, window)

    await handler.handle(
        HandleNutritionTargetUpdatedCommand(
            event_id=uuid.uuid4(), user_id=user_id, protein_g_min=50.0, fat_g_min=44.0
        )
    )

    assert await window.get_current_target_min(user_id, "protein_g") == 50.0
    assert await window.get_current_target_min(user_id, "fat_g") == 44.0


async def test_does_not_mutate_already_persisted_historical_window_rows():
    processed = FakeProcessedNutritionCalculationEventsRepository()
    window = FakeMicronutrientWindowRepository()
    user_id = uuid.uuid4()
    from datetime import date

    await window.upsert(user_id, "protein_g", date(2026, 6, 1), 40.0, target_min=30.0)

    await HandleNutritionTargetUpdatedHandler(processed, window).handle(
        HandleNutritionTargetUpdatedCommand(
            event_id=uuid.uuid4(), user_id=user_id, protein_g_min=99.0, fat_g_min=None
        )
    )

    historical_row = window.window[(user_id, "protein_g", date(2026, 6, 1))]
    assert historical_row["target_min"] == 30.0  # unchanged despite the new current target


async def test_redelivered_event_id_is_a_no_op():
    processed = FakeProcessedNutritionCalculationEventsRepository()
    window = FakeMicronutrientWindowRepository()
    command = HandleNutritionTargetUpdatedCommand(
        event_id=uuid.uuid4(), user_id=uuid.uuid4(), protein_g_min=50.0, fat_g_min=44.0
    )
    handler = HandleNutritionTargetUpdatedHandler(processed, window)

    await handler.handle(command)
    await handler.handle(command)

    assert window.set_current_target_min_calls == len({"protein_g", "fat_g"})
