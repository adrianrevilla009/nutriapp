from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.events.recipe_created import build_recipe_created_event
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository

pytestmark = pytest.mark.usefixtures("db_engine")


@pytest.fixture
async def session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s


async def test_enqueue_and_fetch_unpublished(session):
    outbox = PostgresOutboxRepository(session)
    event = build_recipe_created_event(
        recipe_id=uuid.uuid4(), user_id=uuid.uuid4(), correlation_id="c1"
    )
    await outbox.enqueue(event)
    await session.commit()

    pending = await outbox.fetch_unpublished()
    assert len(pending) == 1
    assert pending[0].event_type == "RecipeCreated"


async def test_mark_published_removes_from_unpublished(session):
    outbox = PostgresOutboxRepository(session)
    event = build_recipe_created_event(
        recipe_id=uuid.uuid4(), user_id=uuid.uuid4(), correlation_id="c1"
    )
    await outbox.enqueue(event)
    await session.commit()

    await outbox.mark_published(event.event_id)
    await session.commit()

    pending = await outbox.fetch_unpublished()
    assert pending == []
