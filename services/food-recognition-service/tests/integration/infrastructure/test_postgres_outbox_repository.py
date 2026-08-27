from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.events.food_photo_analyzed import build_food_photo_analyzed_event
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository

pytestmark = pytest.mark.usefixtures("db_engine")


def _event(analysis_id: uuid.UUID) -> object:
    return build_food_photo_analyzed_event(
        analysis_id=analysis_id,
        user_id=uuid.uuid4(),
        candidates=[],
        model_version="claude-haiku-4-5",
        status="unavailable",
        correlation_id="c1",
        occurred_at=datetime.now(timezone.utc),
    )


async def test_enqueue_and_fetch_unpublished(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        outbox = PostgresOutboxRepository(session)
        event = _event(uuid.uuid4())
        await outbox.enqueue(event)
        await session.commit()

        pending = await outbox.fetch_unpublished()
        assert len(pending) == 1
        assert pending[0].event_type == "FoodPhotoAnalyzed"


async def test_mark_published_removes_from_unpublished(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        outbox = PostgresOutboxRepository(session)
        event = _event(uuid.uuid4())
        await outbox.enqueue(event)
        await session.commit()

        await outbox.mark_published(event.event_id)
        await session.commit()

        pending = await outbox.fetch_unpublished()
        assert pending == []
