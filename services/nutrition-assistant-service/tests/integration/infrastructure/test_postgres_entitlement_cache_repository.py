from __future__ import annotations

import uuid

from infrastructure.persistence.postgres_entitlement_cache_repository import (
    PostgresEntitlementCacheRepository,
)


async def test_get_on_miss_returns_none(session_factory) -> None:
    async with session_factory() as session:
        repo = PostgresEntitlementCacheRepository(session)
        assert await repo.get(uuid.uuid4()) is None


async def test_set_then_get_round_trip(session_factory) -> None:
    user_id = uuid.uuid4()
    async with session_factory() as session:
        repo = PostgresEntitlementCacheRepository(session)
        await repo.set(user_id, True)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresEntitlementCacheRepository(session)
        assert await repo.get(user_id) is True


async def test_set_twice_updates_in_place(session_factory) -> None:
    user_id = uuid.uuid4()
    async with session_factory() as session:
        repo = PostgresEntitlementCacheRepository(session)
        await repo.set(user_id, True)
        await repo.set(user_id, False)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresEntitlementCacheRepository(session)
        assert await repo.get(user_id) is False
