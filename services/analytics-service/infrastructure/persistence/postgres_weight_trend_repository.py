"""Implements domain.ports.weight_trend_repository_port.WeightTrendRepositoryPort.
Stores the AES-256-GCM ciphertext field exactly as received -- never
decrypted here or anywhere else in this service (ADR-0023)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import WeightTrendModel


class PostgresWeightTrendRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self, user_id: uuid.UUID, on_date: date, weight_kg_ciphertext: str, recorded_at: datetime
    ) -> None:
        key = {"user_id": user_id, "on_date": on_date}
        row = await self._session.get(WeightTrendModel, key)
        if row is None:
            row = WeightTrendModel(**key)
            self._session.add(row)
        row.weight_kg_ciphertext = weight_kg_ciphertext
        row.recorded_at = recorded_at
        await self._session.flush()
