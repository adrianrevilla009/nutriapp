from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.persistence.postgres_processed_entitlement_events_repository import (
    PostgresProcessedEntitlementEventsRepository,
)


async def test_unprocessed_event_id_is_not_processed(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        repo = PostgresProcessedEntitlementEventsRepository(session)
        result = await repo.is_processed(uuid.uuid4())
    assert result is False


async def test_mark_processed_then_is_processed_true(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    event_id = uuid.uuid4()

    async with session_factory() as session:
        repo = PostgresProcessedEntitlementEventsRepository(session)
        await repo.mark_processed(event_id)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresProcessedEntitlementEventsRepository(session)
        result = await repo.is_processed(event_id)
    assert result is True


async def test_marking_the_same_event_id_processed_twice_is_safe(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    event_id = uuid.uuid4()

    async with session_factory() as session:
        repo = PostgresProcessedEntitlementEventsRepository(session)
        await repo.mark_processed(event_id)
        await repo.mark_processed(event_id)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresProcessedEntitlementEventsRepository(session)
        result = await repo.is_processed(event_id)
    assert result is True
