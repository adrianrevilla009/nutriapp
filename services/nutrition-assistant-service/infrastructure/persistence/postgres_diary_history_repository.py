"""Implements domain.ports.diary_history_repository_port.DiaryHistoryRepositoryPort."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.value_objects.retrieved_record import RetrievedRecord
from infrastructure.persistence.models import FoodEntryHistoryModel, WaterIntakeHistoryModel


class PostgresDiaryHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_food_entry(
        self, entry_id: uuid.UUID, user_id: uuid.UUID, summary: str, occurred_at: datetime
    ) -> None:
        row = await self._session.get(FoodEntryHistoryModel, entry_id)
        if row is None:
            row = FoodEntryHistoryModel(
                entry_id=entry_id, user_id=user_id, summary=summary, occurred_at=occurred_at
            )
            self._session.add(row)
        else:
            row.summary = summary
            row.occurred_at = occurred_at
        await self._session.flush()

    async def remove_food_entry(self, entry_id: uuid.UUID) -> None:
        row = await self._session.get(FoodEntryHistoryModel, entry_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()

    async def upsert_water_intake(
        self, intake_id: uuid.UUID, user_id: uuid.UUID, summary: str, occurred_at: datetime
    ) -> None:
        row = await self._session.get(WaterIntakeHistoryModel, intake_id)
        if row is None:
            row = WaterIntakeHistoryModel(
                intake_id=intake_id, user_id=user_id, summary=summary, occurred_at=occurred_at
            )
            self._session.add(row)
        else:
            row.summary = summary
            row.occurred_at = occurred_at
        await self._session.flush()

    async def remove_water_intake(self, intake_id: uuid.UUID) -> None:
        row = await self._session.get(WaterIntakeHistoryModel, intake_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()

    async def recent_for_user(self, user_id: uuid.UUID, limit: int = 20) -> list[RetrievedRecord]:
        food_stmt = (
            select(FoodEntryHistoryModel)
            .where(FoodEntryHistoryModel.user_id == user_id)
            .order_by(FoodEntryHistoryModel.occurred_at.desc())
            .limit(limit)
        )
        water_stmt = (
            select(WaterIntakeHistoryModel)
            .where(WaterIntakeHistoryModel.user_id == user_id)
            .order_by(WaterIntakeHistoryModel.occurred_at.desc())
            .limit(limit)
        )
        food_rows = (await self._session.execute(food_stmt)).scalars().all()
        water_rows = (await self._session.execute(water_stmt)).scalars().all()

        records = [
            RetrievedRecord(record_id=str(row.entry_id), source="diary", content=row.summary)
            for row in food_rows
        ]
        records += [
            RetrievedRecord(record_id=str(row.intake_id), source="diary", content=row.summary)
            for row in water_rows
        ]
        return records
