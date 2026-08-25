"""PostgresProcessedEventsRepository -- implements ProcessedEventsPort.

Idempotency dedup for consumed events (messaging-conventions SKILL.md),
currently only UserRegistered. A processed-event record older than
PROCESSED_EVENT_TTL is treated as eligible for reprocessing -- long enough
to exceed realistic RabbitMQ redelivery windows (documented in
profile-service/README.md), short enough that this table does not grow
unbounded (a periodic cleanup job deleting expired rows is a documented
follow-up, not implemented here -- `already_processed` returning False for
an expired row is itself always correct even if the row is never
physically deleted).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import ProcessedInboundEventModel

PROCESSED_EVENT_TTL = timedelta(days=7)


class PostgresProcessedEventsRepository:
    """Implements domain.ports.processed_events_port.ProcessedEventsPort."""

    def __init__(self, session: AsyncSession, ttl: timedelta = PROCESSED_EVENT_TTL) -> None:
        self._session = session
        self._ttl = ttl

    async def already_processed(self, event_id: uuid.UUID) -> bool:
        row = await self._session.get(ProcessedInboundEventModel, event_id)
        if row is None:
            return False
        age = datetime.now(timezone.utc) - row.processed_at
        return age <= self._ttl

    async def mark_processed(self, event_id: uuid.UUID) -> None:
        existing = await self._session.get(ProcessedInboundEventModel, event_id)
        now = datetime.now(timezone.utc)
        if existing is not None:
            existing.processed_at = now
        else:
            self._session.add(ProcessedInboundEventModel(event_id=event_id, processed_at=now))
        await self._session.flush()
