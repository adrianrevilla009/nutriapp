"""Implements domain.ports.nutrition_history_repository_port.NutritionHistoryRepositoryPort."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.value_objects.retrieved_record import RetrievedRecord
from infrastructure.persistence.models import (
    NutritionTargetHistoryModel,
    NutritionValueHistoryModel,
)


class PostgresNutritionHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_value_recomputed(
        self,
        user_id: uuid.UUID,
        scope: str,
        reference_id: str,
        on_date: date | None,
        summary: str,
    ) -> None:
        key = {"user_id": user_id, "scope": scope, "reference_id": reference_id}
        row = await self._session.get(NutritionValueHistoryModel, key)
        if row is None:
            row = NutritionValueHistoryModel(
                user_id=user_id,
                scope=scope,
                reference_id=reference_id,
                on_date=on_date,
                summary=summary,
            )
            self._session.add(row)
        else:
            row.on_date = on_date
            row.summary = summary
        await self._session.flush()

    async def upsert_target_updated(self, user_id: uuid.UUID, summary: str) -> None:
        row = await self._session.get(NutritionTargetHistoryModel, user_id)
        if row is None:
            row = NutritionTargetHistoryModel(user_id=user_id, summary=summary)
            self._session.add(row)
        else:
            row.summary = summary
        await self._session.flush()

    async def recent_for_user(self, user_id: uuid.UUID, limit: int = 20) -> list[RetrievedRecord]:
        value_stmt = (
            select(NutritionValueHistoryModel)
            .where(NutritionValueHistoryModel.user_id == user_id)
            .order_by(NutritionValueHistoryModel.on_date.desc().nullslast())
            .limit(limit)
        )
        value_rows = (await self._session.execute(value_stmt)).scalars().all()
        target_row = await self._session.get(NutritionTargetHistoryModel, user_id)

        records = [
            RetrievedRecord(
                record_id=f"{row.user_id}:{row.scope}:{row.reference_id}",
                source="nutrition",
                content=row.summary,
            )
            for row in value_rows
        ]
        if target_row is not None:
            records.append(
                RetrievedRecord(
                    record_id=f"{target_row.user_id}:target",
                    source="nutrition",
                    content=target_row.summary,
                )
            )
        return records
