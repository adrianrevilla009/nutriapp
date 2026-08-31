from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.events.user_followed import build_user_followed_event
from infrastructure.messaging.outbox_relay_worker import OutboxRelayWorker
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from tests.fixtures.factories import NOW, make_follow

pytestmark = pytest.mark.usefixtures("db_engine")


class _FakePublisher:
    def __init__(self, fail: bool = False) -> None:
        self.published = []
        self.fail = fail

    async def publish(self, event) -> None:
        if self.fail:
            raise RuntimeError("publish failed")
        self.published.append(event)


def _event():
    follow = make_follow()
    return build_user_followed_event(
        follow_id=follow.follow_id,
        follower_id=follow.follower_id,
        followee_id=follow.followee_id,
        followed_at=NOW,
        correlation_id="c1",
    )


async def test_outbox_row_inserted_in_same_transaction_is_relayed(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async with session_factory() as session:
        outbox = PostgresOutboxRepository(session)
        event = _event()
        await outbox.enqueue(event)
        await session.commit()

    publisher = _FakePublisher()
    worker = OutboxRelayWorker(session_factory, publisher)
    published_count = await worker.relay_once()

    assert published_count == 1
    assert publisher.published[0].event_type == "UserFollowed"


async def test_publish_failure_leaves_row_unpublished_for_retry(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async with session_factory() as session:
        outbox = PostgresOutboxRepository(session)
        event = _event()
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
