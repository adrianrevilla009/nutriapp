"""PostgresPendingPushDispatchRepository -- round-trip persistence via
testcontainers Postgres (mirrors
test_postgres_reminder_schedule_repository.py's shape)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from domain.value_objects.pending_dispatch_status import PendingDispatchStatus
from infrastructure.persistence.postgres_pending_push_dispatch_repository import (
    PostgresPendingPushDispatchRepository,
)
from tests.fixtures.factories import make_pending_push_dispatch

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


async def test_add_then_list_due_round_trips(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresPendingPushDispatchRepository(session)
        dispatch = make_pending_push_dispatch(
            context={"follow_id": "f-1"}, earliest_dispatch_at=NOW - timedelta(minutes=5)
        )
        await repo.add(dispatch)
        await session.commit()

        due = await repo.list_due(NOW)
        assert len(due) == 1
        assert due[0].dispatch_id == dispatch.dispatch_id
        assert due[0].user_id == dispatch.user_id
        assert due[0].context == {"follow_id": "f-1"}
        assert due[0].template_id.name == "new_follower"


async def test_list_due_excludes_not_yet_due_rows(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresPendingPushDispatchRepository(session)
        not_due = make_pending_push_dispatch(earliest_dispatch_at=NOW + timedelta(hours=1))
        await repo.add(not_due)
        await session.commit()

        due = await repo.list_due(NOW)
        assert due == []


async def test_list_due_excludes_non_pending_rows(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresPendingPushDispatchRepository(session)
        dispatch = make_pending_push_dispatch(
            earliest_dispatch_at=NOW - timedelta(minutes=5),
            status=PendingDispatchStatus.SENT,
        )
        await repo.add(dispatch)
        await session.commit()

        due = await repo.list_due(NOW)
        assert due == []


async def test_mark_status_updates_status_and_reschedules(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresPendingPushDispatchRepository(session)
        dispatch = make_pending_push_dispatch(earliest_dispatch_at=NOW - timedelta(minutes=5))
        await repo.add(dispatch)
        await session.commit()

        rescheduled = NOW + timedelta(hours=2)
        await repo.mark_status(
            dispatch.dispatch_id, PendingDispatchStatus.PENDING, earliest_dispatch_at=rescheduled
        )
        await session.commit()

        due_now = await repo.list_due(NOW)
        assert due_now == []
        due_later = await repo.list_due(rescheduled)
        assert len(due_later) == 1


async def test_mark_status_sent_removes_row_from_due_list(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresPendingPushDispatchRepository(session)
        dispatch = make_pending_push_dispatch(earliest_dispatch_at=NOW - timedelta(minutes=5))
        await repo.add(dispatch)
        await session.commit()

        await repo.mark_status(dispatch.dispatch_id, PendingDispatchStatus.SENT)
        await session.commit()

        assert await repo.list_due(NOW) == []
