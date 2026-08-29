"""PostgresReminderScheduleRepository -- round-trip persistence via
testcontainers Postgres (test-plan section 2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from domain.value_objects.reminder_status import ReminderStatus
from infrastructure.persistence.postgres_reminder_schedule_repository import (
    PostgresReminderScheduleRepository,
)
from tests.fixtures.factories import make_reminder_entry

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


async def test_upsert_then_get_by_source_round_trips(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresReminderScheduleRepository(session)
        entry = make_reminder_entry(
            due_at=NOW - timedelta(minutes=5), relevance_expires_at=NOW + timedelta(hours=1)
        )
        await repo.upsert(entry)
        await session.commit()

        fetched = await repo.get_by_source(entry.source_aggregate_id, "fasting")
        assert fetched is not None
        assert fetched.user_id == entry.user_id


async def test_upsert_on_same_source_and_category_updates_in_place(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresReminderScheduleRepository(session)
        entry = make_reminder_entry(
            source_aggregate_id="plan-1",
            category_name="meal",
            due_at=NOW,
            relevance_expires_at=NOW + timedelta(hours=1),
        )
        await repo.upsert(entry)
        await session.commit()
        first_id = entry.schedule_id

        entry2 = make_reminder_entry(
            source_aggregate_id="plan-1",
            category_name="meal",
            due_at=NOW + timedelta(hours=2),
            relevance_expires_at=NOW + timedelta(hours=3),
        )
        await repo.upsert(entry2)
        await session.commit()

        fetched = await repo.get_by_source("plan-1", "meal")
        assert fetched.schedule_id == first_id


async def test_remove_by_source(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresReminderScheduleRepository(session)
        entry = make_reminder_entry(
            source_aggregate_id="window-1",
            category_name="fasting",
            due_at=NOW,
            relevance_expires_at=NOW + timedelta(hours=1),
        )
        await repo.upsert(entry)
        await session.commit()

        await repo.remove_by_source("window-1", "fasting")
        await session.commit()

        assert await repo.get_by_source("window-1", "fasting") is None


async def test_list_pending_filters_by_status_and_next_eligible_check(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresReminderScheduleRepository(session)
        due_entry = make_reminder_entry(
            due_at=NOW - timedelta(minutes=5), relevance_expires_at=NOW + timedelta(hours=1)
        )
        delayed_entry = make_reminder_entry(
            due_at=NOW - timedelta(minutes=5),
            relevance_expires_at=NOW + timedelta(hours=1),
            next_eligible_check_at=NOW + timedelta(hours=2),
        )
        await repo.upsert(due_entry)
        await repo.upsert(delayed_entry)
        await session.commit()

        pending = await repo.list_pending(NOW)
        pending_ids = {entry.schedule_id for entry in pending}
        assert due_entry.schedule_id in pending_ids
        assert delayed_entry.schedule_id not in pending_ids


async def test_mark_status_updates_row(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresReminderScheduleRepository(session)
        entry = make_reminder_entry(
            due_at=NOW - timedelta(minutes=5), relevance_expires_at=NOW + timedelta(hours=1)
        )
        await repo.upsert(entry)
        await session.commit()

        await repo.mark_status(entry.schedule_id, ReminderStatus.SENT)
        await session.commit()

        fetched = await repo.get_by_source(entry.source_aggregate_id, "fasting")
        assert fetched.status == ReminderStatus.SENT
