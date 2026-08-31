from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.events.user_followed import build_user_followed_event
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from tests.fixtures.factories import NOW, make_follow


async def test_enqueue_then_fetch_unpublished_round_trips(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    follow = make_follow()
    event = build_user_followed_event(
        follow_id=follow.follow_id,
        follower_id=follow.follower_id,
        followee_id=follow.followee_id,
        followed_at=NOW,
        correlation_id="corr-1",
    )

    async with session_factory() as session:
        repo = PostgresOutboxRepository(session)
        await repo.enqueue(event)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresOutboxRepository(session)
        pending = await repo.fetch_unpublished()

    assert len(pending) == 1
    assert pending[0].event_id == event.event_id
    assert pending[0].payload == event.payload


async def test_mark_published_excludes_from_fetch_unpublished(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    follow = make_follow()
    event = build_user_followed_event(
        follow_id=follow.follow_id,
        follower_id=follow.follower_id,
        followee_id=follow.followee_id,
        followed_at=NOW,
        correlation_id="corr-2",
    )

    async with session_factory() as session:
        repo = PostgresOutboxRepository(session)
        await repo.enqueue(event)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresOutboxRepository(session)
        await repo.mark_published(event.event_id)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresOutboxRepository(session)
        pending = await repo.fetch_unpublished()

    assert pending == []
