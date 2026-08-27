from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.entities.daily_nutrition_total import DailyNutritionTotal
from domain.events.nutrition_value_recomputed import build_nutrition_value_recomputed_event
from domain.value_objects.formula_version import CURRENT_FORMULA_VERSION
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository

pytestmark = pytest.mark.usefixtures("db_engine")


def _event(user_id: uuid.UUID):
    line = DailyNutritionTotal(user_id=user_id, total_date=date(2026, 8, 25)).compute_total()
    return build_nutrition_value_recomputed_event(
        user_id=user_id,
        scope="day",
        entry_id=None,
        total_date=date(2026, 8, 25),
        line=line,
        confidence_range=None,
        formula_version=CURRENT_FORMULA_VERSION,
        reason="food_entry_logged",
        correlation_id="c1",
        recomputed_at=datetime.now(timezone.utc),
    )


async def test_enqueue_and_fetch_unpublished(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        outbox = PostgresOutboxRepository(session)
        event = _event(uuid.uuid4())
        await outbox.enqueue(event)
        await session.commit()

        pending = await outbox.fetch_unpublished()
        assert len(pending) == 1
        assert pending[0].event_type == "NutritionValueRecomputed"


async def test_mark_published_removes_from_unpublished(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        outbox = PostgresOutboxRepository(session)
        event = _event(uuid.uuid4())
        await outbox.enqueue(event)
        await session.commit()

        await outbox.mark_published(event.event_id)
        await session.commit()

        pending = await outbox.fetch_unpublished()
        assert pending == []
