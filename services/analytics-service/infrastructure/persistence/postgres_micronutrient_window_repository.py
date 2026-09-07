"""Implements domain.ports.micronutrient_window_repository_port.MicronutrientWindowRepositoryPort.

`micronutrient_window` rows are immutable snapshots once written (the
`target_min` recorded on a row is whatever was current at upsert time,
never rewritten by a later `set_current_target_min` call) --
`micronutrient_current_targets` is the separate, mutable "what's current
now" table `HandleNutritionTargetUpdatedHandler` updates."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.value_objects.trend_point import TrendPoint
from infrastructure.persistence.models import (
    MicronutrientCurrentTargetModel,
    MicronutrientWindowModel,
)


class PostgresMicronutrientWindowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        user_id: uuid.UUID,
        nutrient: str,
        on_date: date,
        value: float,
        target_min: float | None,
    ) -> None:
        key = {"user_id": user_id, "nutrient": nutrient, "on_date": on_date}
        row = await self._session.get(MicronutrientWindowModel, key)
        if row is None:
            row = MicronutrientWindowModel(**key)
            self._session.add(row)
        row.value = value
        row.target_min = target_min
        await self._session.flush()

    async def list_recent(
        self, user_id: uuid.UUID, nutrient: str, limit_days: int
    ) -> list[TrendPoint]:
        stmt = (
            select(MicronutrientWindowModel)
            .where(
                MicronutrientWindowModel.user_id == user_id,
                MicronutrientWindowModel.nutrient == nutrient,
            )
            .order_by(MicronutrientWindowModel.on_date.desc())
            .limit(limit_days)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [TrendPoint(on_date=row.on_date, value=row.value) for row in rows]

    async def get_current_target_min(self, user_id: uuid.UUID, nutrient: str) -> float | None:
        row = await self._session.get(
            MicronutrientCurrentTargetModel, {"user_id": user_id, "nutrient": nutrient}
        )
        return row.target_min if row is not None else None

    async def set_current_target_min(
        self, user_id: uuid.UUID, nutrient: str, target_min: float | None
    ) -> None:
        key = {"user_id": user_id, "nutrient": nutrient}
        row = await self._session.get(MicronutrientCurrentTargetModel, key)
        if row is None:
            row = MicronutrientCurrentTargetModel(**key)
            self._session.add(row)
        row.target_min = target_min
        await self._session.flush()

    async def list_window(
        self, user_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[dict[str, object]]:
        stmt = (
            select(MicronutrientWindowModel)
            .where(
                MicronutrientWindowModel.user_id == user_id,
                MicronutrientWindowModel.on_date >= start_date,
                MicronutrientWindowModel.on_date <= end_date,
            )
            .order_by(
                MicronutrientWindowModel.on_date.asc(), MicronutrientWindowModel.nutrient.asc()
            )
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            {
                "on_date": row.on_date.isoformat(),
                "nutrient": row.nutrient,
                "value": row.value,
                "target_min": row.target_min,
            }
            for row in rows
        ]
