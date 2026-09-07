"""OutboxRelayWorker -- appending an event and the outbox row happens
atomically; relay marks it published exactly once (test-plan section 3).

Also covers the atomicity failure-mode test flagged missing by
qa-agent's test review: a simulated failure after the DB write but
before/during publish must not lose the event -- `_publish_and_mark`'s
call order (`publish()` then `mark_published()`,
`outbox_relay_worker.py` lines 37-41) means a publish failure must leave
the row unpublished, still returned by a subsequent `fetch_unpublished()`
call, so a future reordering regression (marking published before or
regardless of publish success) would fail this test."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.events.base import DomainEvent, EventMetadata
from infrastructure.messaging.outbox_relay_worker import OutboxRelayWorker
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository


class _FakePublisher:
    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self.published.append(event)


class _AlwaysFailingPublisher:
    """Simulates a publish failure (e.g. a dropped RabbitMQ connection)
    on every call -- never appends to `published`, always raises."""

    def __init__(self) -> None:
        self.publish_attempts = 0

    async def publish(self, event: DomainEvent) -> None:
        self.publish_attempts += 1
        raise ConnectionError("simulated broker failure")


async def test_relay_once_publishes_and_marks_published(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    event = DomainEvent(
        aggregate_id=str(uuid.uuid4()),
        event_type="NutrientDeficiencyDetected",
        version=1,
        payload={"user_id": str(uuid.uuid4())},
        metadata=EventMetadata(correlation_id="corr-1"),
        occurred_at=datetime.now(timezone.utc),
    )

    async with session_factory() as session:
        await PostgresOutboxRepository(session).enqueue(event)
        await session.commit()

    publisher = _FakePublisher()
    worker = OutboxRelayWorker(session_factory, publisher)
    relayed_count = await worker.relay_once()

    assert relayed_count == 1
    assert publisher.published[0].event_id == event.event_id

    async with session_factory() as session:
        still_pending = await PostgresOutboxRepository(session).fetch_unpublished()
    assert still_pending == []


async def test_publish_failure_leaves_event_unpublished_not_lost(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    event = DomainEvent(
        aggregate_id=str(uuid.uuid4()),
        event_type="NutrientDeficiencyDetected",
        version=1,
        payload={"user_id": str(uuid.uuid4())},
        metadata=EventMetadata(correlation_id="corr-2"),
        occurred_at=datetime.now(timezone.utc),
    )

    async with session_factory() as session:
        await PostgresOutboxRepository(session).enqueue(event)
        await session.commit()

    publisher = _AlwaysFailingPublisher()
    worker = OutboxRelayWorker(session_factory, publisher)

    with pytest.raises(ConnectionError):
        await worker.relay_once()

    assert publisher.publish_attempts == 1

    async with session_factory() as session:
        still_pending = await PostgresOutboxRepository(session).fetch_unpublished()
    # mark_published() must never have run -- the event is still pending,
    # not lost, ready to be retried on the next poll (run_forever()'s own
    # try/except around relay_once() is what makes that retry happen in
    # production; relay_once() itself correctly propagates the failure
    # rather than silently swallowing it here).
    assert len(still_pending) == 1
    assert still_pending[0].event_id == event.event_id
