from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.persistence.postgres_processed_events_repository import (
    PostgresProcessedEventsRepository,
)


async def test_dedup_is_scoped_per_consumer_name(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    event_id = uuid.uuid4()

    async with session_factory() as session:
        repo = PostgresProcessedEventsRepository(session)
        assert await repo.already_processed("diary_food_entry", event_id) is False

        await repo.mark_processed("diary_food_entry", event_id)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresProcessedEventsRepository(session)
        assert await repo.already_processed("diary_food_entry", event_id) is True
        # Same event_id, different consumer -- independently tracked.
        assert await repo.already_processed("profile_metrics", event_id) is False
