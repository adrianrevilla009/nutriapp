"""Independent idempotency ledger from
PostgresProcessedEntitlementEventsRepository -- same shape, own table
(implementation plan section 3)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.persistence.postgres_processed_recipe_events_repository import (
    PostgresProcessedRecipeEventsRepository,
)


async def test_not_processed_by_default(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        repo = PostgresProcessedRecipeEventsRepository(session)
        result = await repo.is_processed(uuid.uuid4())
    assert result is False


async def test_mark_processed_then_is_processed_true(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    event_id = uuid.uuid4()

    async with session_factory() as session:
        repo = PostgresProcessedRecipeEventsRepository(session)
        await repo.mark_processed(event_id)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresProcessedRecipeEventsRepository(session)
        result = await repo.is_processed(event_id)
    assert result is True
