from __future__ import annotations

import uuid
from datetime import date

from infrastructure.persistence.postgres_nutrition_history_repository import (
    PostgresNutritionHistoryRepository,
)


async def test_value_recomputed_round_trip(session_factory) -> None:
    user_id = uuid.uuid4()
    async with session_factory() as session:
        repo = PostgresNutritionHistoryRepository(session)
        await repo.upsert_value_recomputed(
            user_id, "day", "2026-09-07", date(2026, 9, 7), "1800 kcal"
        )
        await session.commit()

    async with session_factory() as session:
        repo = PostgresNutritionHistoryRepository(session)
        records = await repo.recent_for_user(user_id)
        assert any(r.content == "1800 kcal" for r in records)


async def test_target_updated_round_trip(session_factory) -> None:
    user_id = uuid.uuid4()
    async with session_factory() as session:
        repo = PostgresNutritionHistoryRepository(session)
        await repo.upsert_target_updated(user_id, "target: 2000 kcal")
        await session.commit()

    async with session_factory() as session:
        repo = PostgresNutritionHistoryRepository(session)
        records = await repo.recent_for_user(user_id)
        assert any(r.content == "target: 2000 kcal" for r in records)


async def test_upsert_same_scope_replaces(session_factory) -> None:
    user_id = uuid.uuid4()
    async with session_factory() as session:
        repo = PostgresNutritionHistoryRepository(session)
        await repo.upsert_value_recomputed(user_id, "entry", "entry-1", None, "first")
        await repo.upsert_value_recomputed(user_id, "entry", "entry-1", None, "second")
        await session.commit()

    async with session_factory() as session:
        repo = PostgresNutritionHistoryRepository(session)
        records = await repo.recent_for_user(user_id)
        entry_records = [r for r in records if "entry-1" in r.record_id]
        assert len(entry_records) == 1
        assert entry_records[0].content == "second"
