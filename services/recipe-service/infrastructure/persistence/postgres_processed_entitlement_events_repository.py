"""PostgresProcessedEntitlementEventsRepository -- implements
ProcessedEntitlementEventsRepositoryPort. Backs `billing_events_consumer.py`'s
idempotency check, keyed by `event_id` alone."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import ProcessedEntitlementEventModel


class PostgresProcessedEntitlementEventsRepository:
    """Implements domain.ports.processed_entitlement_events_repository_port.ProcessedEntitlementEventsRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_processed(self, event_id: uuid.UUID) -> bool:
        row = await self._session.get(ProcessedEntitlementEventModel, event_id)
        return row is not None

    async def mark_processed(self, event_id: uuid.UUID) -> None:
        row = await self._session.get(ProcessedEntitlementEventModel, event_id)
        if row is None:
            row = ProcessedEntitlementEventModel(
                event_id=event_id, processed_at=datetime.now(timezone.utc)
            )
            self._session.add(row)
            await self._session.flush()
