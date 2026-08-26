from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from application.commands.plan_meal import PlanMealCommand, PlanMealHandler
from application.commands.update_meal_plan import UpdateMealPlanCommand, UpdateMealPlanHandler
from application.errors import MealPlanAccessDeniedError, MealPlanEntryNotFoundError
from domain.value_objects.food_source import FoodSource, FoodSourceSnapshot
from domain.value_objects.macro_snapshot import MacroSnapshot
from domain.value_objects.meal_slot import MealSlot
from tests.fixtures.factories import FakeEventStore, FakeOutboxRepository

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


def _source(name: str = "Rice") -> FoodSource:
    return FoodSource(
        source_type="catalog_product",
        source_reference_id="prod-1",
        snapshot=FoodSourceSnapshot(
            name=name,
            brand=None,
            quantity=150.0,
            unit="g",
            macros_per_unit=MacroSnapshot(calories_kcal=200, protein_g=4, carbs_g=45, fat_g=1),
        ),
    )


async def _plan_meal(event_store, outbox, user_id) -> uuid.UUID:
    handler = PlanMealHandler(event_store, outbox)
    result = await handler.handle(
        PlanMealCommand(
            user_id=user_id,
            source=_source(),
            meal_slot=MealSlot.DINNER,
            planned_for=NOW,
            correlation_id="corr-1",
        )
    )
    return result.plan_entry_id


async def test_update_meal_plan_appends_updated_event():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    user_id = uuid.uuid4()
    plan_entry_id = await _plan_meal(event_store, outbox, user_id)

    handler = UpdateMealPlanHandler(event_store, outbox, now_fn=lambda: NOW)
    await handler.handle(
        UpdateMealPlanCommand(
            plan_entry_id=plan_entry_id,
            user_id=user_id,
            source=_source("Quinoa"),
            meal_slot=MealSlot.LUNCH,
            planned_for=NOW,
            correlation_id="corr-2",
        )
    )
    stream = await event_store.load("meal_plan_entry", str(plan_entry_id))
    assert [e.event_type for e in stream] == ["MealPlanned", "MealPlanUpdated"]


async def test_update_unknown_plan_entry_raises_not_found():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    handler = UpdateMealPlanHandler(event_store, outbox, now_fn=lambda: NOW)
    with pytest.raises(MealPlanEntryNotFoundError):
        await handler.handle(
            UpdateMealPlanCommand(
                plan_entry_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                source=_source(),
                meal_slot=MealSlot.LUNCH,
                planned_for=NOW,
                correlation_id="corr-1",
            )
        )


async def test_update_another_users_plan_entry_raises_access_denied():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    owner_id = uuid.uuid4()
    plan_entry_id = await _plan_meal(event_store, outbox, owner_id)
    handler = UpdateMealPlanHandler(event_store, outbox, now_fn=lambda: NOW)
    with pytest.raises(MealPlanAccessDeniedError):
        await handler.handle(
            UpdateMealPlanCommand(
                plan_entry_id=plan_entry_id,
                user_id=uuid.uuid4(),
                source=_source(),
                meal_slot=MealSlot.LUNCH,
                planned_for=NOW,
                correlation_id="corr-2",
            )
        )
