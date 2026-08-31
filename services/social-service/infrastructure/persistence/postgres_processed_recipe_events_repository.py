"""PostgresProcessedRecipeEventsRepository -- implements
ProcessedRecipeEventsRepositoryPort. Backs `recipe_events_consumer.py`'s
idempotency check, keyed by `event_id` alone -- a SEPARATE table/ledger
from `PostgresProcessedEntitlementEventsRepository` (implementation plan
section 3)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import ProcessedRecipeEventModel


class PostgresProcessedRecipeEventsRepository:
    """Implements domain.ports.processed_recipe_events_repository_port.ProcessedRecipeEventsRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_processed(self, event_id: uuid.UUID) -> bool:
        row = await self._session.get(ProcessedRecipeEventModel, event_id)
        return row is not None

    async def mark_processed(self, event_id: uuid.UUID) -> None:
        row = await self._session.get(ProcessedRecipeEventModel, event_id)
        if row is None:
            row = ProcessedRecipeEventModel(
                event_id=event_id, processed_at=datetime.now(timezone.utc)
            )
            self._session.add(row)
            await self._session.flush()
