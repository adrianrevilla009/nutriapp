"""Implements domain.ports.outbox_repository_port.OutboxRepositoryPort.
Scaffolded for architectural symmetry -- unused this pass (implementation
plan section 5, no live publisher)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import OutboxModel


class PostgresOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(self, event: dict[str, Any]) -> None:
        self._session.add(
            OutboxModel(
                event_id=uuid.UUID(event["event_id"]),
                aggregate_id=event["aggregate_id"],
                event_type=event["event_type"],
                version=event["version"],
                payload=event["payload"],
                event_metadata=event.get("metadata", {}),
                occurred_at=datetime.now(UTC),
                published_at=None,
            )
        )
        await self._session.flush()

    async def fetch_unpublished(self, limit: int = 50) -> list[dict[str, Any]]:
        stmt = select(OutboxModel).where(OutboxModel.published_at.is_(None)).limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            {
                "event_id": str(row.event_id),
                "aggregate_id": row.aggregate_id,
                "event_type": row.event_type,
                "version": row.version,
                "payload": row.payload,
                "metadata": row.event_metadata,
            }
            for row in rows
        ]

    async def mark_published(self, event_id: uuid.UUID) -> None:
        row = await self._session.get(OutboxModel, event_id)
        if row is not None:
            row.published_at = datetime.now(UTC)
            await self._session.flush()
