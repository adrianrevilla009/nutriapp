"""PendingPushDispatchScanWorker -- scan_once() against real Postgres,
wiring every repository from the same session (mirrors
test_reminder_scan_worker.py's identical shape). Also exercises the
worker-level idempotency guarantee: a second scan tick after a successful
send must never dispatch the same row twice."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.entities.notification_preference import NotificationPreference
from domain.value_objects.notification_category import NotificationCategory
from domain.value_objects.pending_dispatch_status import PendingDispatchStatus
from infrastructure.persistence.models import PendingPushDispatchModel
from infrastructure.persistence.postgres_pending_push_dispatch_repository import (
    PostgresPendingPushDispatchRepository,
)
from infrastructure.persistence.postgres_preferences_repository import (
    PostgresPreferencesRepository,
)
from infrastructure.scheduling.pending_push_dispatch_scan_worker import (
    PendingPushDispatchScanWorker,
)
from tests.fixtures.factories import (
    FakePushProviderPort,
    FakeTemplateRendererPort,
    make_pending_push_dispatch,
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


async def test_scan_once_sends_a_due_dispatch_and_marks_it_sent(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    push_provider = FakePushProviderPort()

    dispatch = make_pending_push_dispatch(earliest_dispatch_at=NOW - timedelta(minutes=5))
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        await PostgresPendingPushDispatchRepository(session).add(dispatch)
        await PostgresPreferencesRepository(session).upsert(
            NotificationPreference(
                user_id=dispatch.user_id,
                category=NotificationCategory.push("new_follower"),
                push_enabled=True,
            )
        )
        await session.commit()

    worker = PendingPushDispatchScanWorker(
        session_factory, push_provider, FakeTemplateRendererPort()
    )
    await worker.scan_once(now=NOW)

    assert len(push_provider.calls) == 1
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        due = await PostgresPendingPushDispatchRepository(session).list_due(NOW)
        assert due == []


async def test_scanning_twice_dispatches_the_same_row_exactly_once(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    push_provider = FakePushProviderPort()

    dispatch = make_pending_push_dispatch(earliest_dispatch_at=NOW - timedelta(minutes=5))
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        await PostgresPendingPushDispatchRepository(session).add(dispatch)
        await PostgresPreferencesRepository(session).upsert(
            NotificationPreference(
                user_id=dispatch.user_id,
                category=NotificationCategory.push("new_follower"),
                push_enabled=True,
            )
        )
        await session.commit()

    worker = PendingPushDispatchScanWorker(
        session_factory, push_provider, FakeTemplateRendererPort()
    )
    await worker.scan_once(now=NOW)
    await worker.scan_once(now=NOW + timedelta(minutes=1))

    assert len(push_provider.calls) == 1
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        result = await session.get(PendingPushDispatchModel, dispatch.dispatch_id)
        assert result is not None
        assert result.status == PendingDispatchStatus.SENT.value
