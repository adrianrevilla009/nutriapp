"""PostgresProcessedNotificationsRepository -- round-trip persistence,
dedup on (event_id, channel) (test-plan section 2)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.postgres_processed_notifications_repository import (
    PostgresProcessedNotificationsRepository,
)


async def test_mark_processed_then_already_processed(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresProcessedNotificationsRepository(session)
        event_id = uuid.uuid4()

        assert await repo.already_processed(event_id, "email") is False

        await repo.mark_processed(event_id, "email")
        await session.commit()

        assert await repo.already_processed(event_id, "email") is True
        # A different channel for the same event_id is a distinct key.
        assert await repo.already_processed(event_id, "push") is False


async def test_mark_processed_twice_does_not_raise(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresProcessedNotificationsRepository(session)
        event_id = uuid.uuid4()

        await repo.mark_processed(event_id, "push")
        await repo.mark_processed(event_id, "push")
        await session.commit()

        assert await repo.already_processed(event_id, "push") is True
