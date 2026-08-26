from __future__ import annotations

import uuid
from datetime import datetime, timezone

from application.commands.plan_meal import PlanMealCommand, PlanMealHandler
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
            name="Rice",
            brand=None,
            quantity=150.0,
            unit="g",
            macros_per_unit=MacroSnapshot(calories_kcal=200, protein_g=4, carbs_g=45, fat_g=1),
        ),
    )


async def test_plan_meal_appends_planned_event():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    handler = PlanMealHandler(event_store, outbox)

    user_id = uuid.uuid4()
    result = await handler.handle(
        PlanMealCommand(
            user_id=user_id,
            source=_source(),
            meal_slot=MealSlot.DINNER,
            planned_for=NOW,
            correlation_id="corr-1",
        )
    )

    stream = await event_store.load("meal_plan_entry", str(result.plan_entry_id))
    assert len(stream) == 1
    assert stream[0].event_type == "MealPlanned"
