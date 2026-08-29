"""PostgresExerciseRepository integration tests -- round-trip persistence
via testcontainers Postgres (test-plan section 2)."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.value_objects.duration_minutes import DurationMinutes
from infrastructure.persistence.postgres_exercise_repository import PostgresExerciseRepository
from tests.fixtures.factories import make_exercise_entry

pytestmark = pytest.mark.usefixtures("db_engine")


@pytest.fixture
async def session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s


async def test_create_and_get_round_trip(session):
    repo = PostgresExerciseRepository(session)
    user_id = uuid.uuid4()
    entry = make_exercise_entry(user_id=user_id, duration_minutes=40)
    await repo.add(entry)
    await session.commit()

    fetched = await repo.get_by_id_and_user(entry.entry_id, user_id)
    assert fetched is not None
    assert int(fetched.duration) == 40


async def test_update_persists_correction(session):
    repo = PostgresExerciseRepository(session)
    user_id = uuid.uuid4()
    entry = make_exercise_entry(user_id=user_id, duration_minutes=40)
    await repo.add(entry)
    await session.commit()

    later = dt.datetime.now(dt.timezone.utc)
    corrected = entry.corrected(now=later, duration=DurationMinutes(55))
    await repo.update(corrected)
    await session.commit()

    fetched = await repo.get_by_id_and_user(entry.entry_id, user_id)
    assert fetched is not None
    assert int(fetched.duration) == 55


async def test_soft_delete_persists_and_is_excluded_from_list(session):
    repo = PostgresExerciseRepository(session)
    user_id = uuid.uuid4()
    occurred_at = dt.datetime(2026, 8, 20, 7, 0, tzinfo=dt.timezone.utc)
    entry = make_exercise_entry(user_id=user_id, occurred_at=occurred_at)
    await repo.add(entry)
    await session.commit()

    later = dt.datetime.now(dt.timezone.utc)
    deleted = entry.soft_deleted(now=later)
    await repo.update(deleted)
    await session.commit()

    fetched = await repo.get_by_id_and_user(entry.entry_id, user_id)
    assert fetched is not None
    assert fetched.is_deleted is True

    listed = await repo.list_for_user_and_date(user_id, dt.date(2026, 8, 20))
    assert listed == []


async def test_list_for_user_and_date_scopes_by_user_and_day(session):
    repo = PostgresExerciseRepository(session)
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    day = dt.date(2026, 8, 20)

    entry_a = make_exercise_entry(
        user_id=user_a, occurred_at=dt.datetime(2026, 8, 20, 7, 0, tzinfo=dt.timezone.utc)
    )
    entry_a_other_day = make_exercise_entry(
        user_id=user_a, occurred_at=dt.datetime(2026, 8, 21, 7, 0, tzinfo=dt.timezone.utc)
    )
    entry_b = make_exercise_entry(
        user_id=user_b, occurred_at=dt.datetime(2026, 8, 20, 7, 0, tzinfo=dt.timezone.utc)
    )
    for e in (entry_a, entry_a_other_day, entry_b):
        await repo.add(e)
    await session.commit()

    listed = await repo.list_for_user_and_date(user_a, day)
    assert [e.entry_id for e in listed] == [entry_a.entry_id]
