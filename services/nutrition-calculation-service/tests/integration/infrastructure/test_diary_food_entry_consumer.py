"""DiaryFoodEntryConsumer -- idempotency test (test-plan section 2): the
same FoodEntryLogged delivered twice results in exactly one contribution
to the day total, not two."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.messaging.diary_food_entry_consumer import DiaryFoodEntryConsumer
from infrastructure.persistence.postgres_daily_nutrition_total_repository import (
    PostgresDailyNutritionTotalRepository,
)
from tests.fixtures.factories import make_food_entry_logged_payload, wrap_event

pytestmark = pytest.mark.usefixtures("db_engine")


async def test_replayed_food_entry_logged_does_not_double_count(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    consumer = DiaryFoodEntryConsumer(session_factory)

    user_id = uuid.uuid4()
    entry_id = uuid.uuid4()
    occurred_at = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    payload = make_food_entry_logged_payload(
        entry_id=entry_id, user_id=user_id, occurred_at=occurred_at
    )
    body = wrap_event("FoodEntryLogged", payload)

    await consumer.process_body(body)
    await consumer.process_body(body)  # exact same event_id -- a redelivery

    async with session_factory() as session:
        repo = PostgresDailyNutritionTotalRepository(session)
        total = await repo.get(user_id, date(2026, 8, 25))

    assert total is not None
    assert total.compute_total().macros.calories_kcal == 300.0  # 200 kcal/100g x 150g, once
    assert len(total.entries) == 1


async def test_food_entry_deleted_removes_the_entry(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    consumer = DiaryFoodEntryConsumer(session_factory)

    user_id = uuid.uuid4()
    entry_id = uuid.uuid4()
    occurred_at = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    logged_payload = make_food_entry_logged_payload(
        entry_id=entry_id, user_id=user_id, occurred_at=occurred_at
    )
    await consumer.process_body(wrap_event("FoodEntryLogged", logged_payload))

    deleted_payload = {
        "entry_id": str(entry_id),
        "user_id": str(user_id),
        "deleted_at": datetime.now(timezone.utc).isoformat(),
    }
    await consumer.process_body(wrap_event("FoodEntryDeleted", deleted_payload))

    async with session_factory() as session:
        repo = PostgresDailyNutritionTotalRepository(session)
        total = await repo.get(user_id, date(2026, 8, 25))

    assert total is not None
    assert entry_id not in total.entries
    assert total.compute_total().macros.calories_kcal == 0.0


async def test_replayed_food_entry_deleted_is_a_safe_no_op(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    consumer = DiaryFoodEntryConsumer(session_factory)

    user_id = uuid.uuid4()
    entry_id = uuid.uuid4()

    deleted_payload = {
        "entry_id": str(entry_id),
        "user_id": str(user_id),
        "deleted_at": datetime.now(timezone.utc).isoformat(),
    }
    # Never logged in the first place -- deleting is a safe no-op, not an error.
    await consumer.process_body(wrap_event("FoodEntryDeleted", deleted_payload))
