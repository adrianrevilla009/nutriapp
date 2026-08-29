"""OutboxRelayWorker integration tests -- appending an event and the
outbox row happens atomically; a simulated failure after the DB write but
before the publish must not lose the event (still relayed on retry), per
messaging-conventions SKILL.md's Testing Requirements and test-plan
section 2."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.events.exercise_logged import build_exercise_logged_event
from infrastructure.messaging.outbox_relay_worker import OutboxRelayWorker
from infrastructure.persistence.postgres_exercise_repository import PostgresExerciseRepository
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from tests.fixtures.factories import make_exercise_entry

pytestmark = pytest.mark.usefixtures("db_engine")


class _FakePublisher:
    def __init__(self, fail: bool = False) -> None:
        self.published = []
        self.fail = fail

    async def publish(self, event) -> None:
        if self.fail:
            raise RuntimeError("publish failed")
        self.published.append(event)


async def test_outbox_row_inserted_in_same_transaction_is_relayed(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async with session_factory() as session:
        repo = PostgresExerciseRepository(session)
        entry = make_exercise_entry()
        await repo.add(entry)
        outbox = PostgresOutboxRepository(session)
        event = build_exercise_logged_event(entry=entry, correlation_id="c1")
        await outbox.enqueue(event)
        await session.commit()

    publisher = _FakePublisher()
    worker = OutboxRelayWorker(session_factory, publisher)
    published_count = await worker.relay_once()

    assert published_count == 1
    assert publisher.published[0].event_type == "ExerciseLogged"


async def test_publish_failure_leaves_row_unpublished_for_retry(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async with session_factory() as session:
        repo = PostgresExerciseRepository(session)
        entry = make_exercise_entry()
        await repo.add(entry)
        outbox = PostgresOutboxRepository(session)
        event = build_exercise_logged_event(entry=entry, correlation_id="c1")
        await outbox.enqueue(event)
        await session.commit()

    failing_publisher = _FakePublisher(fail=True)
    worker = OutboxRelayWorker(session_factory, failing_publisher)
    with pytest.raises(RuntimeError):
        await worker.relay_once()

    async with session_factory() as session:
        outbox = PostgresOutboxRepository(session)
        pending = await outbox.fetch_unpublished()
    assert len(pending) == 1

    # Retry succeeds -- the event was never lost by the simulated
    # post-write-pre-publish failure above.
    recovering_publisher = _FakePublisher()
    retry_worker = OutboxRelayWorker(session_factory, recovering_publisher)
    published_count = await retry_worker.relay_once()
    assert published_count == 1
    assert recovering_publisher.published[0].event_type == "ExerciseLogged"
