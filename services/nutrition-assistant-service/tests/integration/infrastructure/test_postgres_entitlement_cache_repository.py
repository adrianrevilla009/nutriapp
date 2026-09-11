from __future__ import annotations

import uuid
from datetime import UTC, datetime

from infrastructure.persistence.models import EntitlementCacheModel
from infrastructure.persistence.postgres_entitlement_cache_repository import (
    PostgresEntitlementCacheRepository,
)


async def test_get_on_miss_returns_none(session_factory) -> None:
    async with session_factory() as session:
        repo = PostgresEntitlementCacheRepository(session)
        assert await repo.get(uuid.uuid4()) is None


async def test_upsert_then_get_round_trip(session_factory) -> None:
    user_id = uuid.uuid4()
    async with session_factory() as session:
        repo = PostgresEntitlementCacheRepository(session)
        await repo.upsert(user_id, True, datetime.now(UTC))
        await session.commit()

    async with session_factory() as session:
        repo = PostgresEntitlementCacheRepository(session)
        assert await repo.get(user_id) is True


async def test_upsert_twice_updates_in_place_not_a_second_row(session_factory) -> None:
    user_id = uuid.uuid4()
    async with session_factory() as session:
        repo = PostgresEntitlementCacheRepository(session)
        await repo.upsert(user_id, True, datetime.now(UTC))
        await repo.upsert(user_id, False, datetime.now(UTC))
        await session.commit()

    async with session_factory() as session:
        repo = PostgresEntitlementCacheRepository(session)
        assert await repo.get(user_id) is False


async def test_upsert_persists_the_events_own_occurred_at_not_wall_clock_time(
    session_factory,
) -> None:
    user_id = uuid.uuid4()
    occurred_at = datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC)
    async with session_factory() as session:
        repo = PostgresEntitlementCacheRepository(session)
        await repo.upsert(user_id, True, occurred_at)
        await session.commit()

    async with session_factory() as session:
        row = await session.get(EntitlementCacheModel, user_id)
        assert row is not None
        assert row.updated_at == occurred_at
