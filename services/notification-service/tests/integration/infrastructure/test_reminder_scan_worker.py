"""ReminderScanWorker -- scan_once() against real Postgres, wiring every
repository from the same session (test-plan section 2's persistence
round-trip coverage extended to the worker itself, not just the
handler's fake-port unit tests)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.entities.notification_preference import NotificationPreference
from domain.value_objects.notification_category import NotificationCategory
from domain.value_objects.reminder_status import ReminderStatus
from infrastructure.persistence.postgres_preferences_repository import (
    PostgresPreferencesRepository,
)
from infrastructure.persistence.postgres_reminder_schedule_repository import (
    PostgresReminderScheduleRepository,
)
from infrastructure.scheduling.reminder_scan_worker import ReminderScanWorker
from tests.fixtures.factories import (
    FakePushProviderPort,
    FakeTemplateRendererPort,
    make_reminder_entry,
)

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


async def test_scan_once_sends_a_due_reminder_and_marks_it_sent(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    push_provider = FakePushProviderPort()

    entry = make_reminder_entry(
        due_at=NOW - timedelta(minutes=5), relevance_expires_at=NOW + timedelta(hours=1)
    )
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        await PostgresReminderScheduleRepository(session).upsert(entry)
        await PostgresPreferencesRepository(session).upsert(
            NotificationPreference(
                user_id=entry.user_id,
                category=NotificationCategory.push("fasting"),
                push_enabled=True,
            )
        )
        await session.commit()

    worker = ReminderScanWorker(
        session_factory,
        push_provider,
        FakeTemplateRendererPort(),
    )
    # Explicit `now` passthrough -- pins the scan instant to the same NOW
    # the seeded entry's due_at/relevance_expires_at were computed
    # relative to, instead of racing the real wall clock.
    await worker.scan_once(now=NOW)

    assert len(push_provider.calls) == 1
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        fetched = await PostgresReminderScheduleRepository(session).get_by_source(
            entry.source_aggregate_id, "fasting"
        )
        assert fetched.status == ReminderStatus.SENT
