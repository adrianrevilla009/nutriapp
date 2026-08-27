from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.meal_plan_entry import MealPlanEntry
from domain.value_objects.food_source import FoodSource, FoodSourceSnapshot
from domain.value_objects.macro_snapshot import MacroSnapshot
from domain.value_objects.meal_slot import MealSlot
from infrastructure.persistence.projectors.meal_plan_projector import PostgresMealPlanProjector

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


@pytest.fixture
async def session(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as s:
        yield s


def _source(name: str) -> FoodSource:
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


async def test_replaying_fixed_event_sequence_produces_expected_row(session):
    plan_entry_id = uuid.uuid4()
    user_id = uuid.uuid4()
    entry, planned = MealPlanEntry.plan(
        plan_entry_id=plan_entry_id,
        user_id=user_id,
        source=_source("Rice"),
        meal_slot=MealSlot.DINNER,
        planned_for=NOW,
        correlation_id="corr-1",
    )
    updated = entry.update(
        source=_source("Quinoa"),
        meal_slot=MealSlot.LUNCH,
        planned_for=NOW,
        updated_at=NOW,
        correlation_id="corr-2",
    )

    projector = PostgresMealPlanProjector(session)
    await projector.apply(planned)
    await projector.apply(updated)
    await session.commit()

    rows = await projector.get_calendar(user_id, date(2026, 8, 1), date(2026, 8, 31))
    assert len(rows) == 1
    assert rows[0]["source"]["snapshot"]["name"] == "Quinoa"
    assert rows[0]["meal_slot"] == "lunch"
