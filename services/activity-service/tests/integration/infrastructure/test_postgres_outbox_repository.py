"""PostgresOutboxRepository integration tests (test-plan section 2)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.events.exercise_logged import build_exercise_logged_event
from infrastructure.persistence.postgres_exercise_repository import PostgresExerciseRepository
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from tests.fixtures.factories import make_exercise_entry

pytestmark = pytest.mark.usefixtures("db_engine")


@pytest.fixture
async def session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s


async def test_enqueue_and_fetch_unpublished(session):
    repo = PostgresExerciseRepository(session)
    entry = make_exercise_entry()
    await repo.add(entry)

    outbox = PostgresOutboxRepository(session)
    event = build_exercise_logged_event(entry=entry, correlation_id="c1")
    await outbox.enqueue(event)
    await session.commit()

    pending = await outbox.fetch_unpublished()
    assert len(pending) == 1
    assert pending[0].event_type == "ExerciseLogged"


async def test_mark_published_removes_from_unpublished(session):
    repo = PostgresExerciseRepository(session)
    entry = make_exercise_entry()
    await repo.add(entry)

    outbox = PostgresOutboxRepository(session)
    event = build_exercise_logged_event(entry=entry, correlation_id="c1")
    await outbox.enqueue(event)
    await session.commit()

    await outbox.mark_published(event.event_id)
    await session.commit()

    pending = await outbox.fetch_unpublished()
    assert pending == []
