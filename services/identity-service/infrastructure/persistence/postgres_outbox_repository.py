"""PostgresOutboxRepository — implements OutboxRepositoryPort.

Outbox pattern (messaging-conventions SKILL.md): `enqueue()` must run in
the same DB transaction/session as the triggering write so both commit or
neither does. Callers (application handlers) share one AsyncSession per
request via the composition root, so `session.flush()` here participates
in that same transaction; the caller commits once, at the end of the
request.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.events.base import DomainEvent, EventMetadata
from infrastructure.persistence.models import OutboxModel


def _to_domain(row: OutboxModel) -> DomainEvent:
    return DomainEvent(
        event_id=row.event_id,
        event_type=row.event_type,
        version=row.version,
        aggregate_id=row.aggregate_id,
        payload=row.payload,
        metadata=EventMetadata(**row.event_metadata),
        occurred_at=row.occurred_at,
    )


class PostgresOutboxRepository:
    """Implements domain.ports.outbox_repository_port.OutboxRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(self, event: DomainEvent) -> None:
        row = OutboxModel(
            event_id=event.event_id,
            event_type=event.event_type,
            version=event.version,
            aggregate_id=event.aggregate_id,
            payload=event.payload,
            event_metadata={
                "correlation_id": event.metadata.correlation_id,
                "causation_id": event.metadata.causation_id,
                "user_id": event.metadata.user_id,
            },
            occurred_at=event.occurred_at,
            published_at=None,
        )
        self._session.add(row)
        await self._session.flush()

    async def fetch_unpublished(self, limit: int = 100) -> list[DomainEvent]:
        stmt = (
            select(OutboxModel)
            .where(OutboxModel.published_at.is_(None))
            .order_by(OutboxModel.occurred_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [_to_domain(row) for row in result.scalars()]

    async def mark_published(self, event_id: uuid.UUID) -> None:
        row = await self._session.get(OutboxModel, event_id)
        if row is not None:
            row.published_at = datetime.now(timezone.utc)
            await self._session.flush()
