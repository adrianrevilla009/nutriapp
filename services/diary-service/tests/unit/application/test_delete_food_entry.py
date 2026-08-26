from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from application.commands.delete_food_entry import DeleteFoodEntryCommand, DeleteFoodEntryHandler
from application.commands.log_food_entry import LogFoodEntryCommand, LogFoodEntryHandler
from application.errors import FoodEntryAccessDeniedError, FoodEntryNotFoundError
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


async def _log_entry(event_store, outbox, user_id) -> uuid.UUID:
    handler = LogFoodEntryHandler(event_store, outbox, now_fn=lambda: NOW)
    result = await handler.handle(
        LogFoodEntryCommand(
            user_id=user_id,
            source=_source(),
            meal_slot=MealSlot.BREAKFAST,
            occurred_at=NOW,
            correlation_id="corr-1",
        )
    )
    return result.entry_id


async def test_delete_food_entry_appends_deleted_event():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    user_id = uuid.uuid4()
    entry_id = await _log_entry(event_store, outbox, user_id)

    handler = DeleteFoodEntryHandler(event_store, outbox, now_fn=lambda: NOW)
    result = await handler.handle(
        DeleteFoodEntryCommand(entry_id=entry_id, user_id=user_id, correlation_id="corr-2")
    )
    assert result.deleted is True
    stream = await event_store.load("food_entry", str(entry_id))
    assert stream[-1].event_type == "FoodEntryDeleted"


async def test_delete_unknown_entry_raises_not_found():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    handler = DeleteFoodEntryHandler(event_store, outbox, now_fn=lambda: NOW)
    with pytest.raises(FoodEntryNotFoundError):
        await handler.handle(
            DeleteFoodEntryCommand(
                entry_id=uuid.uuid4(), user_id=uuid.uuid4(), correlation_id="corr-1"
            )
        )


async def test_delete_another_users_entry_raises_access_denied():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    owner_id = uuid.uuid4()
    entry_id = await _log_entry(event_store, outbox, owner_id)
    handler = DeleteFoodEntryHandler(event_store, outbox, now_fn=lambda: NOW)
    with pytest.raises(FoodEntryAccessDeniedError):
        await handler.handle(
            DeleteFoodEntryCommand(entry_id=entry_id, user_id=uuid.uuid4(), correlation_id="corr-2")
        )
