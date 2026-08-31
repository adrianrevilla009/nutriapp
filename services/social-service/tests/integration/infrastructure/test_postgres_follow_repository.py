"""PostgresFollowRepository -- round-trip persistence via testcontainers
Postgres (test-plan section 2). Explicitly tests the `(follower_id,
followee_id)` unique constraint is enforced at the DB level -- defense-in-
depth beneath the application-layer idempotency check."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.persistence.postgres_follow_repository import PostgresFollowRepository
from tests.fixtures.factories import NOW, make_follow


async def test_save_and_get_round_trips(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    follow = make_follow()

    async with session_factory() as session:
        repo = PostgresFollowRepository(session)
        await repo.save(follow)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresFollowRepository(session)
        fetched = await repo.get(follow.follower_id, follow.followee_id)

    assert fetched is not None
    assert fetched.follow_id == follow.follow_id
    assert fetched.followed_at == follow.followed_at


async def test_get_missing_returns_none(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        repo = PostgresFollowRepository(session)
        result = await repo.get(uuid.uuid4(), uuid.uuid4())
    assert result is None


async def test_delete_removes_row(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    follow = make_follow()

    async with session_factory() as session:
        repo = PostgresFollowRepository(session)
        await repo.save(follow)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresFollowRepository(session)
        await repo.delete(follow.follow_id)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresFollowRepository(session)
        result = await repo.get(follow.follower_id, follow.followee_id)
    assert result is None


async def test_list_following_and_list_followers(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    follower_id = uuid.uuid4()
    followee_id = uuid.uuid4()
    other_followee_id = uuid.uuid4()
    first = make_follow(follower_id=follower_id, followee_id=followee_id)
    second = make_follow(follower_id=follower_id, followee_id=other_followee_id)

    async with session_factory() as session:
        repo = PostgresFollowRepository(session)
        await repo.save(first)
        await repo.save(second)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresFollowRepository(session)
        following = await repo.list_following(follower_id)
        followers = await repo.list_followers(followee_id)

    assert {f.followee_id for f in following} == {followee_id, other_followee_id}
    assert [f.follow_id for f in followers] == [first.follow_id]


async def test_unique_constraint_enforced_at_db_level(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    follower_id = uuid.uuid4()
    followee_id = uuid.uuid4()
    first = make_follow(follower_id=follower_id, followee_id=followee_id, now=NOW)
    second = make_follow(follower_id=follower_id, followee_id=followee_id, now=NOW)

    async with session_factory() as session:
        repo = PostgresFollowRepository(session)
        await repo.save(first)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresFollowRepository(session)
        with pytest.raises(IntegrityError):
            await repo.save(second)  # save() flushes -- constraint violation raises here
