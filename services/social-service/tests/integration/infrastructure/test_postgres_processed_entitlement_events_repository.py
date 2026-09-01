"""PostgresProcessedEntitlementEventsRepository -- against a real
(testcontainers) Postgres."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.persistence.postgres_processed_entitlement_events_repository import (
    PostgresProcessedEntitlementEventsRepository,
)


@pytest.fixture
def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


async def test_an_event_id_that_was_never_marked_is_not_processed(session_factory):
    async with session_factory() as session:
        result = await PostgresProcessedEntitlementEventsRepository(session).is_processed(
            uuid.uuid4()
        )
    assert result is False


@pytest.mark.parametrize("mark_count", [1, 2, 5])
async def test_marking_processed_any_number_of_times_leaves_it_processed(
    session_factory, mark_count: int
):
    event_id = uuid.uuid4()

    async with session_factory() as session:
        repo = PostgresProcessedEntitlementEventsRepository(session)
        for _ in range(mark_count):
            await repo.mark_processed(event_id)
        await session.commit()

    async with session_factory() as session:
        result = await PostgresProcessedEntitlementEventsRepository(session).is_processed(event_id)
    assert result is True
