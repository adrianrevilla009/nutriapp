"""Postgres-backed round trip for the most complex adapter: entry-oriented
apply/correct/remove operations against a real DB, including the
ledger-based exact-reversal behavior (test-plan section 3)."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.postgres_daily_log_summary_repository import (
    PostgresDailyLogSummaryRepository,
)

DAY = date(2026, 6, 8)


async def test_apply_correct_remove_round_trip(db_engine):
    user_id = uuid.uuid4()
    entry_id = uuid.uuid4()

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresDailyLogSummaryRepository(session)
        await repo.apply_food_entry(entry_id, user_id, DAY, 500.0, 30.0, 40.0, 10.0)
        await session.commit()

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresDailyLogSummaryRepository(session)
        rows = await repo.list_window(user_id, DAY, DAY)
        assert rows[0].calories_kcal == 500.0

        await repo.correct_food_entry(entry_id, user_id, DAY, 300.0, 20.0, 25.0, 5.0)
        await session.commit()

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresDailyLogSummaryRepository(session)
        rows = await repo.list_window(user_id, DAY, DAY)
        assert rows[0].calories_kcal == 300.0  # replaced, not added

        await repo.remove_food_entry(entry_id)
        await session.commit()

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresDailyLogSummaryRepository(session)
        rows = await repo.list_window(user_id, DAY, DAY)
        # The day row itself persists (list_window has no non-zero filter),
        # but its macros are fully reversed to zero -- never negative.
        assert rows[0].calories_kcal == 0.0
        assert rows[0].protein_g == 0.0


async def test_water_apply_and_remove_round_trip(db_engine):
    user_id = uuid.uuid4()
    intake_id = uuid.uuid4()

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresDailyLogSummaryRepository(session)
        await repo.apply_water_intake(intake_id, user_id, DAY, 300.0)
        await session.commit()

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresDailyLogSummaryRepository(session)
        rows = await repo.list_window(user_id, DAY, DAY)
        assert rows[0].water_ml == 300.0

        await repo.remove_water_intake(intake_id)
        await session.commit()
