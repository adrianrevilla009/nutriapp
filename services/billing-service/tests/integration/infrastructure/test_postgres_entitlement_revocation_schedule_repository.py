import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.persistence.postgres_entitlement_revocation_schedule_repository import (
    PostgresEntitlementRevocationScheduleRepository,
)

pytestmark = pytest.mark.usefixtures("db_engine")

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


@pytest.fixture
async def session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s


async def test_upsert_pending_then_list_due(session):
    repo = PostgresEntitlementRevocationScheduleRepository(session)
    user_id = uuid.uuid4()
    await repo.upsert_pending(user_id, NOW - timedelta(hours=1))
    await session.commit()

    due = await repo.list_due(NOW)
    assert len(due) == 1
    assert due[0].user_id == user_id
    assert due[0].processed is False


async def test_not_yet_due_row_excluded(session):
    repo = PostgresEntitlementRevocationScheduleRepository(session)
    user_id = uuid.uuid4()
    await repo.upsert_pending(user_id, NOW + timedelta(days=1))
    await session.commit()

    due = await repo.list_due(NOW)
    assert due == []


async def test_mark_processed_excludes_from_future_scans(session):
    repo = PostgresEntitlementRevocationScheduleRepository(session)
    user_id = uuid.uuid4()
    await repo.upsert_pending(user_id, NOW - timedelta(hours=1))
    await session.commit()

    await repo.mark_processed(user_id)
    await session.commit()

    due = await repo.list_due(NOW)
    assert due == []


async def test_upsert_pending_does_not_resurrect_processed_row(session):
    repo = PostgresEntitlementRevocationScheduleRepository(session)
    user_id = uuid.uuid4()
    await repo.upsert_pending(user_id, NOW - timedelta(hours=1))
    await session.commit()
    await repo.mark_processed(user_id)
    await session.commit()

    # A replayed customer.subscription.deleted for the same user must not
    # un-process an already-finalized revocation.
    await repo.upsert_pending(user_id, NOW + timedelta(days=1))
    await session.commit()

    due = await repo.list_due(NOW + timedelta(days=2))
    assert due == []
