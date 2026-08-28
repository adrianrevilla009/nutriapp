"""PostgresSuppressionRepository -- round-trip persistence (test-plan
section 2)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domain.value_objects.notification_category import Channel
from domain.value_objects.suppression_reason import SuppressionReason
from infrastructure.persistence.postgres_suppression_repository import (
    PostgresSuppressionRepository,
)


async def test_add_then_is_suppressed(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresSuppressionRepository(session)
        user_id = uuid.uuid4()

        assert await repo.is_suppressed(user_id, Channel.EMAIL, "user@example.com") is False

        await repo.add(user_id, Channel.EMAIL, "user@example.com", SuppressionReason.HARD_BOUNCE)
        await session.commit()

        assert await repo.is_suppressed(user_id, Channel.EMAIL, "user@example.com") is True


async def test_add_is_idempotent_on_repeated_calls(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresSuppressionRepository(session)
        user_id = uuid.uuid4()

        await repo.add(user_id, Channel.PUSH, str(user_id), SuppressionReason.UNSUBSCRIBE)
        await repo.add(user_id, Channel.PUSH, str(user_id), SuppressionReason.UNSUBSCRIBE)
        await session.commit()

        assert await repo.is_suppressed(user_id, Channel.PUSH, str(user_id)) is True
