from __future__ import annotations

import uuid
from datetime import UTC, datetime

from infrastructure.persistence.postgres_diary_history_repository import (
    PostgresDiaryHistoryRepository,
)


async def test_upsert_and_recent_for_user_round_trip(session_factory) -> None:
    async with session_factory() as session:
        repo = PostgresDiaryHistoryRepository(session)
        user_id = uuid.uuid4()
        entry_id = uuid.uuid4()
        await repo.upsert_food_entry(entry_id, user_id, "200g rice", datetime.now(UTC))
        await session.commit()

    async with session_factory() as session:
        repo = PostgresDiaryHistoryRepository(session)
        records = await repo.recent_for_user(user_id)
        assert len(records) == 1
        assert records[0].content == "200g rice"
        assert records[0].source == "diary"


async def test_upsert_twice_replaces_not_duplicates(session_factory) -> None:
    async with session_factory() as session:
        repo = PostgresDiaryHistoryRepository(session)
        user_id = uuid.uuid4()
        entry_id = uuid.uuid4()
        await repo.upsert_food_entry(entry_id, user_id, "200g rice", datetime.now(UTC))
        await repo.upsert_food_entry(entry_id, user_id, "corrected: 150g rice", datetime.now(UTC))
        await session.commit()

    async with session_factory() as session:
        repo = PostgresDiaryHistoryRepository(session)
        records = await repo.recent_for_user(user_id)
        assert len(records) == 1
        assert records[0].content == "corrected: 150g rice"


async def test_remove_food_entry_is_idempotent(session_factory) -> None:
    async with session_factory() as session:
        repo = PostgresDiaryHistoryRepository(session)
        entry_id = uuid.uuid4()
        await repo.remove_food_entry(entry_id)  # never existed -- must not raise
        await session.commit()


async def test_water_intake_round_trip(session_factory) -> None:
    async with session_factory() as session:
        repo = PostgresDiaryHistoryRepository(session)
        user_id = uuid.uuid4()
        intake_id = uuid.uuid4()
        await repo.upsert_water_intake(intake_id, user_id, "500ml water", datetime.now(UTC))
        await session.commit()

    async with session_factory() as session:
        repo = PostgresDiaryHistoryRepository(session)
        records = await repo.recent_for_user(user_id)
        assert any(r.content == "500ml water" for r in records)


async def test_recent_for_user_scoped_to_user(session_factory) -> None:
    async with session_factory() as session:
        repo = PostgresDiaryHistoryRepository(session)
        user_a, user_b = uuid.uuid4(), uuid.uuid4()
        await repo.upsert_food_entry(uuid.uuid4(), user_a, "user A food", datetime.now(UTC))
        await repo.upsert_food_entry(uuid.uuid4(), user_b, "user B food", datetime.now(UTC))
        await session.commit()

    async with session_factory() as session:
        repo = PostgresDiaryHistoryRepository(session)
        records_a = await repo.recent_for_user(user_a)
        assert len(records_a) == 1
        assert records_a[0].content == "user A food"
