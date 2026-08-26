from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from application.commands.correct_food_entry import (
    CorrectFoodEntryCommand,
    CorrectFoodEntryHandler,
)
from application.commands.log_food_entry import LogFoodEntryCommand, LogFoodEntryHandler
from application.errors import FoodEntryAccessDeniedError, FoodEntryNotFoundError
from domain.value_objects.food_source import FoodSource, FoodSourceSnapshot
from domain.value_objects.macro_snapshot import MacroSnapshot
from domain.value_objects.meal_slot import MealSlot
from tests.fixtures.factories import FakeEventStore, FakeOutboxRepository

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


def _source(name: str = "Oats") -> FoodSource:
    return FoodSource(
        source_type="catalog_product",
        source_reference_id="prod-1",
        snapshot=FoodSourceSnapshot(
            name=name,
            brand=None,
            quantity=100.0,
            unit="g",
            macros_per_unit=MacroSnapshot(calories_kcal=100, protein_g=5, carbs_g=10, fat_g=2),
        ),
    )


async def _log_entry(event_store, outbox, user_id) -> uuid.UUID:
    log_handler = LogFoodEntryHandler(event_store, outbox, now_fn=lambda: NOW)
    result = await log_handler.handle(
        LogFoodEntryCommand(
            user_id=user_id,
            source=_source(),
            meal_slot=MealSlot.BREAKFAST,
            occurred_at=NOW,
            correlation_id="corr-1",
        )
    )
    return result.entry_id


async def test_correct_food_entry_appends_corrected_event():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    user_id = uuid.uuid4()
    entry_id = await _log_entry(event_store, outbox, user_id)

    handler = CorrectFoodEntryHandler(event_store, outbox, now_fn=lambda: NOW)
    await handler.handle(
        CorrectFoodEntryCommand(
            entry_id=entry_id,
            user_id=user_id,
            source=_source("Rice"),
            meal_slot=MealSlot.LUNCH,
            occurred_at=NOW,
            correlation_id="corr-2",
        )
    )

    stream = await event_store.load("food_entry", str(entry_id))
    assert [e.event_type for e in stream] == ["FoodEntryLogged", "FoodEntryCorrected"]


async def test_correct_unknown_entry_raises_not_found():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    handler = CorrectFoodEntryHandler(event_store, outbox, now_fn=lambda: NOW)

    with pytest.raises(FoodEntryNotFoundError):
        await handler.handle(
            CorrectFoodEntryCommand(
                entry_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                source=_source(),
                meal_slot=MealSlot.LUNCH,
                occurred_at=NOW,
                correlation_id="corr-2",
            )
        )


async def test_correct_another_users_entry_raises_access_denied():
    event_store = FakeEventStore()
    outbox = FakeOutboxRepository()
    owner_id = uuid.uuid4()
    entry_id = await _log_entry(event_store, outbox, owner_id)

    handler = CorrectFoodEntryHandler(event_store, outbox, now_fn=lambda: NOW)
    with pytest.raises(FoodEntryAccessDeniedError):
        await handler.handle(
            CorrectFoodEntryCommand(
                entry_id=entry_id,
                user_id=uuid.uuid4(),
                source=_source(),
                meal_slot=MealSlot.LUNCH,
                occurred_at=NOW,
                correlation_id="corr-2",
            )
        )
