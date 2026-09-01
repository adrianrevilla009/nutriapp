"""PostgresFeedRepository -- round-trip persistence via testcontainers
Postgres, including the author-id join `list_for_authors` needs for
`GET /feed`."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.persistence.postgres_feed_repository import PostgresFeedRepository
from tests.fixtures.factories import make_feed_entry


async def test_upsert_and_list_for_authors_round_trips(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    author_id = uuid.uuid4()
    entry = make_feed_entry(author_id=author_id, title="Omelette")

    async with session_factory() as session:
        repo = PostgresFeedRepository(session)
        await repo.upsert(entry)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresFeedRepository(session)
        results = await repo.list_for_authors([author_id])

    assert len(results) == 1
    assert results[0].recipe_id == entry.recipe_id
    assert results[0].title == "Omelette"


async def test_upsert_is_keyed_by_recipe_id_no_duplicate_rows(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    recipe_id = uuid.uuid4()
    author_id = uuid.uuid4()
    first = make_feed_entry(recipe_id=recipe_id, author_id=author_id, title="Draft Title")
    second = make_feed_entry(recipe_id=recipe_id, author_id=author_id, title="Final Title")

    async with session_factory() as session:
        repo = PostgresFeedRepository(session)
        await repo.upsert(first)
        await repo.upsert(second)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresFeedRepository(session)
        results = await repo.list_for_authors([author_id])

    assert len(results) == 1
    assert results[0].title == "Final Title"


async def test_delete_by_recipe_id_removes_row(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    entry = make_feed_entry()

    async with session_factory() as session:
        repo = PostgresFeedRepository(session)
        await repo.upsert(entry)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresFeedRepository(session)
        await repo.delete_by_recipe_id(entry.recipe_id)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresFeedRepository(session)
        results = await repo.list_for_authors([entry.author_id])

    assert results == []


async def test_delete_by_recipe_id_missing_row_is_a_safe_no_op(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        repo = PostgresFeedRepository(session)
        await repo.delete_by_recipe_id(uuid.uuid4())
        await session.commit()


async def test_list_for_authors_with_empty_list_returns_empty_without_query(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        repo = PostgresFeedRepository(session)
        results = await repo.list_for_authors([])
    assert results == []
