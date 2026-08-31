from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.persistence.postgres_entitlement_cache_repository import (
    PostgresEntitlementCacheRepository,
)

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


async def test_get_missing_returns_none(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        repo = PostgresEntitlementCacheRepository(session)
        result = await repo.get(uuid.uuid4())
    assert result is None


async def test_upsert_then_get_round_trips(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    user_id = uuid.uuid4()

    async with session_factory() as session:
        repo = PostgresEntitlementCacheRepository(session)
        await repo.upsert(user_id, True, NOW)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresEntitlementCacheRepository(session)
        result = await repo.get(user_id)
    assert result is True


async def test_upsert_overwrites_existing_row(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    user_id = uuid.uuid4()

    async with session_factory() as session:
        repo = PostgresEntitlementCacheRepository(session)
        await repo.upsert(user_id, True, NOW)
        await repo.upsert(user_id, False, NOW)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresEntitlementCacheRepository(session)
        result = await repo.get(user_id)
    assert result is False
