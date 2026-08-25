from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.events.base import DomainEvent, EventMetadata
from infrastructure.persistence.models import OutboxModel
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository


@pytest.fixture()
async def session(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as s:
        yield s


def make_event() -> DomainEvent:
    return DomainEvent(
        event_type="WeightRecorded",
        version=1,
        aggregate_id=str(uuid.uuid4()),
        payload=dict(user_id="x"),
        metadata=EventMetadata(correlation_id="corr-1", user_id="x"),
    )


async def test_enqueue_and_row_insert_are_atomic_with_the_triggering_write(session, db_engine):
    repo = PostgresOutboxRepository(session)
    event = make_event()
    await repo.enqueue(event)
    await session.rollback()  # simulated failure before commit

    async with AsyncSession(db_engine) as verify_session:
        result = await verify_session.execute(
            select(OutboxModel).where(OutboxModel.event_id == event.event_id)
        )
        assert result.scalar_one_or_none() is None


async def test_fetch_unpublished_then_mark_published_does_not_republish(session):
    repo = PostgresOutboxRepository(session)
    event = make_event()
    await repo.enqueue(event)
    await session.commit()

    pending_before = await repo.fetch_unpublished()
    assert any(e.event_id == event.event_id for e in pending_before)

    await repo.mark_published(event.event_id)
    await session.commit()

    pending_after = await repo.fetch_unpublished()
    assert not any(e.event_id == event.event_id for e in pending_after)


async def test_simulated_crash_mid_relay_does_not_lose_the_event(session, db_engine):
    repo = PostgresOutboxRepository(session)
    event = make_event()
    await repo.enqueue(event)
    await session.commit()

    pending = await repo.fetch_unpublished()
    assert any(e.event_id == event.event_id for e in pending)
    # "Crash" here -- no mark_published call.

    async with AsyncSession(db_engine) as retry_session:
        retry_repo = PostgresOutboxRepository(retry_session)
        still_pending = await retry_repo.fetch_unpublished()
        assert any(e.event_id == event.event_id for e in still_pending)
