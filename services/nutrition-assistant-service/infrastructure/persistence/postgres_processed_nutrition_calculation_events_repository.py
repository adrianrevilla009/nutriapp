"""Implements domain.ports.processed_nutrition_calculation_events_repository_port.ProcessedNutritionCalculationEventsRepositoryPort."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import ProcessedNutritionCalculationEventModel


class PostgresNutritionCalculationEventsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def already_processed(self, event_id: uuid.UUID) -> bool:
        row = await self._session.get(ProcessedNutritionCalculationEventModel, event_id)
        return row is not None

    async def mark_processed(self, event_id: uuid.UUID) -> None:
        row = await self._session.get(ProcessedNutritionCalculationEventModel, event_id)
        if row is None:
            self._session.add(
                ProcessedNutritionCalculationEventModel(
                    event_id=event_id, processed_at=datetime.now(UTC)
                )
            )
            await self._session.flush()
