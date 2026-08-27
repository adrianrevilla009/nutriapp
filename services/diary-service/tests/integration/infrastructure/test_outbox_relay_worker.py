from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.events.base import DomainEvent, EventMetadata
from infrastructure.messaging.outbox_relay_worker import OutboxRelayWorker
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository


class FakePublisher:
    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self.published.append(event)


class FailingPublisher:
    async def publish(self, event: DomainEvent) -> None:
        raise RuntimeError("simulated publish failure")


@pytest.fixture
def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


def make_event() -> DomainEvent:
    return DomainEvent(
        event_type="FoodEntryLogged",
        version=1,
        aggregate_id=str(uuid.uuid4()),
        payload=dict(user_id=str(uuid.uuid4())),
        metadata=EventMetadata(correlation_id="corr-1"),
    )


async def test_relay_once_publishes_pending_events_and_marks_them_published(session_factory):
    event = make_event()
    async with session_factory() as session:
        await PostgresOutboxRepository(session).enqueue(event)
        await session.commit()

    publisher = FakePublisher()
    worker = OutboxRelayWorker(session_factory, publisher)
    count = await worker.relay_once()

    assert count == 1
    assert publisher.published[0].event_id == event.event_id

    async with session_factory() as session:
        pending = await PostgresOutboxRepository(session).fetch_unpublished()
        assert pending == []


async def test_relay_once_does_not_republish_already_published_rows(session_factory):
    event = make_event()
    async with session_factory() as session:
        await PostgresOutboxRepository(session).enqueue(event)
        await session.commit()

    publisher = FakePublisher()
    worker = OutboxRelayWorker(session_factory, publisher)
    await worker.relay_once()
    second_count = await worker.relay_once()

    assert second_count == 0
    assert len(publisher.published) == 1


async def test_publish_failure_leaves_the_event_retryable(session_factory):
    event = make_event()
    async with session_factory() as session:
        await PostgresOutboxRepository(session).enqueue(event)
        await session.commit()

    worker = OutboxRelayWorker(session_factory, FailingPublisher())
    with pytest.raises(RuntimeError):
        await worker.relay_once()

    async with session_factory() as session:
        pending = await PostgresOutboxRepository(session).fetch_unpublished()
        assert len(pending) == 1
