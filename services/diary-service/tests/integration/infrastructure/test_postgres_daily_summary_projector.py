"""PostgresDailySummaryProjector: given a mixed sequence of
FoodEntryLogged, WaterIntakeLogged, and a FastingWindowEnded all on the
same day for one user, produces a correctly aggregated daily summary row
(test-plan section 2) -- exercises at least one event from each of the
(food/water/fasting) entity families feeding this projector."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.fasting_window import FastingWindow
from domain.entities.food_entry import FoodEntry
from domain.entities.water_intake_entry import WaterIntakeEntry
from domain.value_objects.food_source import FoodSource, FoodSourceSnapshot
from domain.value_objects.macro_snapshot import MacroSnapshot
from domain.value_objects.meal_slot import MealSlot
from domain.value_objects.water_amount_ml import WaterAmountMl
from infrastructure.messaging.diary_event_projector_consumer import apply_event_to_read_models
from infrastructure.persistence.projectors.daily_summary_projector import (
    PostgresDailySummaryProjector,
)

NOW = datetime(2026, 8, 26, 8, 0, tzinfo=timezone.utc)


@pytest.fixture
async def session(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as s:
        yield s


def _source() -> FoodSource:
    return FoodSource(
        source_type="catalog_product",
        source_reference_id="prod-1",
        snapshot=FoodSourceSnapshot(
            name="Oats",
            brand=None,
            quantity=100.0,
            unit="g",
            macros_per_unit=MacroSnapshot(calories_kcal=300, protein_g=10, carbs_g=40, fat_g=8),
        ),
    )


async def test_mixed_event_sequence_produces_correctly_aggregated_summary(session):
    user_id = uuid.uuid4()

    _food_entry, food_logged = FoodEntry.log(
        entry_id=uuid.uuid4(),
        user_id=user_id,
        source=_source(),
        meal_slot=MealSlot.BREAKFAST,
        occurred_at=NOW,
        correlation_id="corr-1",
    )
    _water_entry, water_logged = WaterIntakeEntry.log(
        intake_id=uuid.uuid4(),
        user_id=user_id,
        amount=WaterAmountMl(500.0),
        occurred_at=NOW,
        correlation_id="corr-2",
    )
    fasting = FastingWindow.rebuild(user_id, [])
    window_id = uuid.uuid4()
    started = fasting.start_window(window_id, NOW - timedelta(hours=16), "corr-3")
    rebuilt_fasting = FastingWindow.rebuild(user_id, [started])
    ended = rebuilt_fasting.end_window(window_id, NOW, "corr-4")

    for event in [food_logged, water_logged, started, ended]:
        await apply_event_to_read_models(session, event, redis_cache=None)
    await session.commit()

    summary_projector = PostgresDailySummaryProjector(session)
    summary = await summary_projector.get_summary(user_id, NOW.date())
    assert summary is not None
    assert summary["total_calories_kcal"] == 300
    assert summary["total_water_ml"] == 500.0
    assert summary["fasting_windows_ended"] == 1


async def test_apply_returns_touched_user_and_date_or_none_for_irrelevant_events(session):
    user_id = uuid.uuid4()
    _water_entry, water_logged = WaterIntakeEntry.log(
        intake_id=uuid.uuid4(),
        user_id=user_id,
        amount=WaterAmountMl(200.0),
        occurred_at=NOW,
        correlation_id="corr-1",
    )
    summary_projector = PostgresDailySummaryProjector(session)
    touched = await summary_projector.apply(water_logged)
    await session.commit()
    assert touched == (user_id, NOW.date())

    fasting = FastingWindow.rebuild(user_id, [])
    started = fasting.start_window(uuid.uuid4(), NOW, "corr-2")
    touched_by_started = await summary_projector.apply(started)
    assert touched_by_started is None
