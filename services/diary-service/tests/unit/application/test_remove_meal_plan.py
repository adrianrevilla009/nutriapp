from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from application.commands.plan_meal import PlanMealCommand, PlanMealHandler
from application.commands.remove_meal_plan import RemoveMealPlanCommand, RemoveMealPlanHandler
from application.errors import MealPlanAccessDeniedError, MealPlanEntryNotFoundError
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


async def test_remove_meal_plan_appends_removed_event():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    user_id = uuid.uuid4()
    plan_entry_id = await _plan_meal(event_store, outbox, user_id)

    handler = RemoveMealPlanHandler(event_store, outbox, now_fn=lambda: NOW)
    result = await handler.handle(
        RemoveMealPlanCommand(plan_entry_id=plan_entry_id, user_id=user_id, correlation_id="corr-2")
    )
    assert result.removed is True


async def test_remove_unknown_plan_entry_raises_not_found():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    handler = RemoveMealPlanHandler(event_store, outbox, now_fn=lambda: NOW)
    with pytest.raises(MealPlanEntryNotFoundError):
        await handler.handle(
            RemoveMealPlanCommand(
                plan_entry_id=uuid.uuid4(), user_id=uuid.uuid4(), correlation_id="corr-1"
            )
        )


async def test_remove_another_users_plan_entry_raises_access_denied():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    owner_id = uuid.uuid4()
    plan_entry_id = await _plan_meal(event_store, outbox, owner_id)
    handler = RemoveMealPlanHandler(event_store, outbox, now_fn=lambda: NOW)
    with pytest.raises(MealPlanAccessDeniedError):
        await handler.handle(
            RemoveMealPlanCommand(
                plan_entry_id=plan_entry_id, user_id=uuid.uuid4(), correlation_id="corr-2"
            )
        )
