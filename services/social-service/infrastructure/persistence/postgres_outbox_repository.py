"""social-service's own implementation of `OutboxRepositoryPort`, one of
this codebase's repo-wide Outbox Pattern adapters (messaging-conventions
SKILL.md) -- independently written per service (CLAUDE.md section 2.5),
not imported from anywhere shared."""

from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.events.base import DomainEvent, EventMetadata
from infrastructure.persistence.models import OutboxModel


class PostgresOutboxRepository:
    """Implements domain.ports.outbox_repository_port.OutboxRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(self, event: DomainEvent) -> None:
        self._session.add(self._to_row(event))
        await self._session.flush()

    async def fetch_unpublished(self, limit: int = 100) -> list[DomainEvent]:
        stmt = (
            select(OutboxModel)
            .where(OutboxModel.published_at.is_(None))
            .order_by(OutboxModel.occurred_at.asc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_domain_event(row) for row in rows]

    async def mark_published(self, event_id: uuid.UUID) -> None:
        row = await self._session.get(OutboxModel, event_id)
        if row is None:
            return
        row.published_at = datetime.now(timezone.utc)
        await self._session.flush()

    @staticmethod
    def _to_row(event: DomainEvent) -> OutboxModel:
        """Flattens `event.metadata` into the JSONB `metadata` column --
        `dataclasses.asdict` is safe here only because `EventMetadata` is a
        plain, flat dataclass (domain/events/base.py)."""
        return OutboxModel(
            event_id=event.event_id,
            event_type=event.event_type,
            version=event.version,
            aggregate_id=event.aggregate_id,
            payload=event.payload,
            event_metadata=dataclasses.asdict(event.metadata),
            occurred_at=event.occurred_at,
            published_at=None,
        )

    @staticmethod
    def _to_domain_event(row: OutboxModel) -> DomainEvent:
        return DomainEvent(
            event_id=row.event_id,
            event_type=row.event_type,
            version=row.version,
            aggregate_id=row.aggregate_id,
            payload=row.payload,
            metadata=EventMetadata(**row.event_metadata),
            occurred_at=row.occurred_at,
        )
