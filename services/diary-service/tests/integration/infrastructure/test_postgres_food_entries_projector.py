"""Mandatory projector-replay test (cqrs-event-sourcing SKILL.md): a fixed
sequence of events, replayed through PostgresFoodEntriesProjector.apply(),
must produce the exact expected food_entries_view row."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.food_entry import FoodEntry
from domain.value_objects.food_source import FoodSource, FoodSourceSnapshot
from domain.value_objects.macro_snapshot import MacroSnapshot
from domain.value_objects.meal_slot import MealSlot
from infrastructure.persistence.projectors.food_entries_projector import (
    PostgresFoodEntriesProjector,
)

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


@pytest.fixture
async def session(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as s:
        yield s


def _source(name: str, calories: float) -> FoodSource:
    return FoodSource(
        source_type="catalog_product",
        source_reference_id="prod-1",
        snapshot=FoodSourceSnapshot(
            name=name,
            brand=None,
            quantity=100.0,
            unit="g",
            macros_per_unit=MacroSnapshot(calories_kcal=calories, protein_g=5, carbs_g=10, fat_g=2),
        ),
    )


async def test_replaying_fixed_event_sequence_produces_expected_row(session):
    entry_id = uuid.uuid4()
    user_id = uuid.uuid4()
    entry, logged = FoodEntry.log(
        entry_id=entry_id,
        user_id=user_id,
        source=_source("Oats", 100),
        meal_slot=MealSlot.BREAKFAST,
        occurred_at=NOW,
        correlation_id="corr-1",
    )
    corrected = entry.correct(
        source=_source("Steel-Cut Oats", 150),
        meal_slot=MealSlot.LUNCH,
        occurred_at=NOW,
        corrected_at=NOW,
        correlation_id="corr-2",
    )

    projector = PostgresFoodEntriesProjector(session)
    await projector.apply(logged)
    await projector.apply(corrected)
    await session.commit()

    rows = await projector.list_entries(user_id, None, None)
    assert len(rows) == 1
    assert rows[0]["meal_slot"] == "lunch"
    assert rows[0]["source"]["snapshot"]["name"] == "Steel-Cut Oats"
    assert rows[0]["deleted"] is False


async def test_deleted_entry_is_flagged_not_removed(session):
    entry_id = uuid.uuid4()
    user_id = uuid.uuid4()
    entry, logged = FoodEntry.log(
        entry_id=entry_id,
        user_id=user_id,
        source=_source("Oats", 100),
        meal_slot=MealSlot.BREAKFAST,
        occurred_at=NOW,
        correlation_id="corr-1",
    )
    deleted = entry.delete(deleted_at=NOW, correlation_id="corr-2")

    projector = PostgresFoodEntriesProjector(session)
    await projector.apply(logged)
    await projector.apply(deleted)
    await session.commit()

    rows = await projector.list_entries(user_id, None, None)
    assert len(rows) == 1
    assert rows[0]["deleted"] is True


async def test_apply_is_idempotent_under_replay(session):
    entry_id = uuid.uuid4()
    user_id = uuid.uuid4()
    _entry, logged = FoodEntry.log(
        entry_id=entry_id,
        user_id=user_id,
        source=_source("Oats", 100),
        meal_slot=MealSlot.BREAKFAST,
        occurred_at=NOW,
        correlation_id="corr-1",
    )

    projector = PostgresFoodEntriesProjector(session)
    await projector.apply(logged)
    await projector.apply(logged)  # redelivered
    await session.commit()

    rows = await projector.list_entries(user_id, None, None)
    assert len(rows) == 1
