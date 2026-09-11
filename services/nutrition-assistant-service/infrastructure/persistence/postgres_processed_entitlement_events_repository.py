"""Implements
domain.ports.processed_entitlement_events_repository_port.ProcessedEntitlementEventsRepositoryPort."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import ProcessedEntitlementEventModel


class PostgresEntitlementEventsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def already_processed(self, event_id: uuid.UUID) -> bool:
        row = await self._session.get(ProcessedEntitlementEventModel, event_id)
        return row is not None

    async def mark_processed(self, event_id: uuid.UUID) -> None:
        row = await self._session.get(ProcessedEntitlementEventModel, event_id)
        if row is None:
            self._session.add(
                ProcessedEntitlementEventModel(event_id=event_id, processed_at=datetime.now(UTC))
            )
            await self._session.flush()
