"""PostgresEntitlementCacheRepository -- against a real (testcontainers)
Postgres. `session_factory` is scoped once per test module's `db_engine`
so each test opens its own short-lived session per read/write instead of
repeating `async_sessionmaker(db_engine, ...)` inline."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.persistence.postgres_entitlement_cache_repository import (
    PostgresEntitlementCacheRepository,
)

UPDATED_AT = datetime(2026, 6, 1, tzinfo=timezone.utc)


@pytest.fixture
def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


async def test_get_on_a_row_that_was_never_written_returns_none(session_factory):
    async with session_factory() as session:
        result = await PostgresEntitlementCacheRepository(session).get(uuid.uuid4())
    assert result is None


@pytest.mark.parametrize(
    "writes,expected_after",
    [
        pytest.param([True], True, id="single-write-round-trips"),
        pytest.param([True, False], False, id="second-write-overwrites-the-first"),
    ],
)
async def test_get_reflects_the_most_recent_upsert(
    session_factory, writes: list[bool], expected_after: bool
):
    user_id = uuid.uuid4()

    async with session_factory() as session:
        repo = PostgresEntitlementCacheRepository(session)
        for entitled in writes:
            await repo.upsert(user_id, entitled, UPDATED_AT)
        await session.commit()

    async with session_factory() as session:
        result = await PostgresEntitlementCacheRepository(session).get(user_id)
    assert result is expected_after
