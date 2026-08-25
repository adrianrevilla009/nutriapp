from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import ProcessedInboundEventModel
from infrastructure.persistence.postgres_processed_events_repository import (
    PostgresProcessedEventsRepository,
)


@pytest.fixture()
async def session(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as s:
        yield s


async def test_already_processed_round_trip(session):
    repo = PostgresProcessedEventsRepository(session)
    event_id = uuid.uuid4()

    assert await repo.already_processed(event_id) is False
    await repo.mark_processed(event_id)
    await session.commit()
    assert await repo.already_processed(event_id) is True


async def test_expired_processed_record_is_eligible_for_reprocessing(session):
    repo = PostgresProcessedEventsRepository(session, ttl=timedelta(days=7))
    event_id = uuid.uuid4()
    stale_timestamp = datetime.now(timezone.utc) - timedelta(days=30)
    session.add(ProcessedInboundEventModel(event_id=event_id, processed_at=stale_timestamp))
    await session.commit()

    assert await repo.already_processed(event_id) is False
