from __future__ import annotations

import uuid
from datetime import datetime, timezone

from application.commands.log_food_entry import LogFoodEntryCommand, LogFoodEntryHandler
from domain.value_objects.food_source import FoodSource, FoodSourceSnapshot
from domain.value_objects.macro_snapshot import MacroSnapshot
from domain.value_objects.meal_slot import MealSlot
from tests.fixtures.factories import FakeEventStore, FakeOutboxRepository

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


def _source() -> FoodSource:
    return FoodSource(
        source_type="catalog_product",
        source_reference_id="prod-1",
        snapshot=FoodSourceSnapshot(
            name="Oats",
            brand=None,
            quantity=100.0,
            unit="g",
            macros_per_unit=MacroSnapshot(calories_kcal=100, protein_g=5, carbs_g=10, fat_g=2),
        ),
    )


async def test_log_food_entry_appends_event_and_enqueues_outbox():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    handler = LogFoodEntryHandler(event_store, outbox, now_fn=lambda: NOW)

    user_id = uuid.uuid4()
    result = await handler.handle(
        LogFoodEntryCommand(
            user_id=user_id,
            source=_source(),
            meal_slot=MealSlot.BREAKFAST,
            occurred_at=NOW,
            correlation_id="corr-1",
        )
    )

    stream = await event_store.load("food_entry", str(result.entry_id))
    assert len(stream) == 1
    assert stream[0].event_type == "FoodEntryLogged"
    assert len(outbox.enqueued) == 1
