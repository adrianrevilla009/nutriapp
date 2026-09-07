"""Implements
domain.ports.processed_diary_events_repository_port.ProcessedDiaryEventsRepositoryPort --
independent idempotency ledger for the diary-events consumer."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import ProcessedDiaryEventModel


class PostgresProcessedDiaryEventsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_processed(self, event_id: uuid.UUID) -> bool:
        row = await self._session.get(ProcessedDiaryEventModel, event_id)
        return row is not None

    async def mark_processed(self, event_id: uuid.UUID) -> None:
        row = await self._session.get(ProcessedDiaryEventModel, event_id)
        if row is not None:
            return
        self._session.add(
            ProcessedDiaryEventModel(event_id=event_id, processed_at=datetime.now(timezone.utc))
        )
        await self._session.flush()
