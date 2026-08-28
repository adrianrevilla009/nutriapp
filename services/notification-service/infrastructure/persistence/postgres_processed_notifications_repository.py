"""PostgresProcessedNotificationsRepository -- implements
ProcessedNotificationsRepositoryPort. Dedup on (event_id, channel)
(CLAUDE.md section 2.4 / notification-agent.md) -- mandatory for every
consumer in this service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import ProcessedNotificationModel


class PostgresProcessedNotificationsRepository:
    """Implements
    domain.ports.processed_notifications_repository_port.ProcessedNotificationsRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def already_processed(self, event_id: uuid.UUID, channel: str) -> bool:
        result = await self._session.execute(
            select(ProcessedNotificationModel).where(
                ProcessedNotificationModel.event_id == event_id,
                ProcessedNotificationModel.channel == channel,
            )
        )
        return result.scalar_one_or_none() is not None

    async def mark_processed(self, event_id: uuid.UUID, channel: str) -> None:
        stmt = insert(ProcessedNotificationModel).values(
            event_id=event_id, channel=channel, processed_at=datetime.now(timezone.utc)
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["event_id", "channel"])
        await self._session.execute(stmt)
        await self._session.flush()
