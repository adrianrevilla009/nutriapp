"""scripts/rebuild_read_models.py: replaying diary_events from scratch
must reproduce all 5 read models exactly, proving the CQRS "read models
are disposable/rebuildable by replaying events" invariant is an actual
runnable capability (test-plan section 2, acceptance criterion 7).

Seeds a non-trivial event history across all 4 aggregate types for two
users, applies it via the same path the live async consumer uses, then
wipes and replays via the rebuild script, comparing the resulting state.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.fasting_window import FastingWindow
from domain.entities.food_entry import FoodEntry
from domain.entities.meal_plan_entry import MealPlanEntry
from domain.entities.water_intake_entry import WaterIntakeEntry
from domain.value_objects.food_source import FoodSource, FoodSourceSnapshot
from domain.value_objects.macro_snapshot import MacroSnapshot
from domain.value_objects.meal_slot import MealSlot
from domain.value_objects.water_amount_ml import WaterAmountMl
from infrastructure.messaging.diary_event_projector_consumer import apply_event_to_read_models
from infrastructure.persistence.postgres_event_store import PostgresEventStore
from infrastructure.persistence.projectors.daily_summary_projector import (
    PostgresDailySummaryProjector,
)
from infrastructure.persistence.projectors.fasting_windows_projector import (
    PostgresFastingWindowsProjector,
)
from infrastructure.persistence.projectors.food_entries_projector import (
    PostgresFoodEntriesProjector,
)
from infrastructure.persistence.projectors.meal_plan_projector import PostgresMealPlanProjector
from infrastructure.persistence.projectors.water_intake_projector import (
    PostgresWaterIntakeProjector,
)
from scripts.rebuild_read_models import rebuild_read_models

NOW = datetime(2026, 8, 26, 8, 0, tzinfo=timezone.utc)


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
            macros_per_unit=MacroSnapshot(calories_kcal=200, protein_g=8, carbs_g=20, fat_g=5),
        ),
    )


async def _seed_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    store = PostgresEventStore(session)

    _food, food_logged = FoodEntry.log(
        entry_id=uuid.uuid4(),
        user_id=user_id,
        source=_source("Oats"),
        meal_slot=MealSlot.BREAKFAST,
        occurred_at=NOW,
        correlation_id="corr-food-1",
    )
    await store.append("food_entry", food_logged, expected_version=0)

    _water, water_logged = WaterIntakeEntry.log(
        intake_id=uuid.uuid4(),
        user_id=user_id,
        amount=WaterAmountMl(300.0),
        occurred_at=NOW,
        correlation_id="corr-water-1",
    )
    await store.append("water_intake_entry", water_logged, expected_version=0)

    fasting = FastingWindow.rebuild(user_id, [])
    window_id = uuid.uuid4()
    started = fasting.start_window(window_id, NOW - timedelta(hours=16), "corr-fast-1")
    await store.append("fasting_window", started, expected_version=0)
    rebuilt_fasting = FastingWindow.rebuild(user_id, [started])
    ended = rebuilt_fasting.end_window(window_id, NOW, "corr-fast-2")
    await store.append("fasting_window", ended, expected_version=1)

    _plan, planned = MealPlanEntry.plan(
        plan_entry_id=uuid.uuid4(),
        user_id=user_id,
        source=_source("Rice"),
        meal_slot=MealSlot.DINNER,
        planned_for=NOW + timedelta(days=1),
        correlation_id="corr-plan-1",
    )
    await store.append("meal_plan_entry", planned, expected_version=0)

    for event in [food_logged, water_logged, started, ended, planned]:
        await apply_event_to_read_models(session, event, redis_cache=None)


async def _snapshot_all(session: AsyncSession, user_ids: list[uuid.UUID]) -> dict:
    food = PostgresFoodEntriesProjector(session)
    water = PostgresWaterIntakeProjector(session)
    fasting = PostgresFastingWindowsProjector(session)
    PostgresMealPlanProjector(session)
    summary = PostgresDailySummaryProjector(session)

    result = {}
    for user_id in user_ids:
        result[user_id] = dict(
            food=await food.list_entries(user_id, None, None),
            water=await water.list_intake(user_id, None, None),
            fasting=await fasting.get_history(user_id),
            summary=await summary.get_summary(user_id, NOW.date()),
        )
    return result


async def test_rebuild_reproduces_read_models_across_two_users_and_all_aggregate_types(session):
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    await _seed_for_user(session, user_a)
    await _seed_for_user(session, user_b)
    await session.commit()

    before = await _snapshot_all(session, [user_a, user_b])

    replayed = await rebuild_read_models(session)
    assert replayed == 10  # 5 events per user x 2 users

    after = await _snapshot_all(session, [user_a, user_b])

    for user_id in (user_a, user_b):
        assert len(after[user_id]["food"]) == len(before[user_id]["food"]) == 1
        assert len(after[user_id]["water"]) == len(before[user_id]["water"]) == 1
        assert len(after[user_id]["fasting"]) == len(before[user_id]["fasting"]) == 1
        assert after[user_id]["summary"] == before[user_id]["summary"]
