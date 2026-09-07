"""Postgres-backed entitlement cache round trip -- get returns None for a
genuine miss, distinguishable from a cached False (test-plan section 3)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.postgres_entitlement_cache_repository import (
    PostgresEntitlementCacheRepository,
)


async def test_get_returns_none_for_genuine_miss(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresEntitlementCacheRepository(session)
        assert await repo.get(uuid.uuid4()) is None


async def test_upsert_then_get_round_trip(db_engine):
    user_id = uuid.uuid4()

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresEntitlementCacheRepository(session)
        await repo.upsert(user_id, True, datetime.now(timezone.utc))
        await session.commit()

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresEntitlementCacheRepository(session)
        assert await repo.get(user_id) is True

        await repo.upsert(user_id, False, datetime.now(timezone.utc))
        await session.commit()

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresEntitlementCacheRepository(session)
        assert await repo.get(user_id) is False
