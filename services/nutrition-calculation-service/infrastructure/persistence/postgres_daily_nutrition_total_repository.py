"""PostgresDailyNutritionTotalRepository -- implements
DailyNutritionTotalRepositoryPort. Upsert-by-`(user_id, date)`
(implementation plan section 2). Round-trips the full per-entry breakdown
(`entries` JSONB) so a later correction/deletion can be applied without
replaying the day's full event history."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.daily_nutrition_total import DailyNutritionTotal
from infrastructure.persistence.mappers import (
    nutrient_total_line_from_dict,
    nutrient_total_line_to_dict,
)
from infrastructure.persistence.models import DailyNutritionTotalModel


def _to_domain(row: DailyNutritionTotalModel) -> DailyNutritionTotal:
    entries = {
        uuid.UUID(entry_id): nutrient_total_line_from_dict(line_data)
        for entry_id, line_data in row.entries.items()
    }
    return DailyNutritionTotal(user_id=row.user_id, total_date=row.total_date, entries=entries)


class PostgresDailyNutritionTotalRepository:
    """Implements
    domain.ports.daily_nutrition_total_repository_port.DailyNutritionTotalRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: uuid.UUID, total_date: date) -> DailyNutritionTotal | None:
        row = await self._session.get(DailyNutritionTotalModel, (user_id, total_date))
        return _to_domain(row) if row is not None else None

    async def upsert(self, total: DailyNutritionTotal) -> None:
        row = await self._session.get(DailyNutritionTotalModel, (total.user_id, total.total_date))
        if row is None:
            row = DailyNutritionTotalModel(user_id=total.user_id, total_date=total.total_date)
            self._session.add(row)

        day_line = total.compute_total()
        row.calories_kcal = day_line.macros.calories_kcal
        row.protein_g = day_line.macros.protein_g
        row.carbs_g = day_line.macros.carbs_g
        row.fat_g = day_line.macros.fat_g
        row.micronutrients = (
            dict(day_line.micronutrients) if day_line.micronutrients is not None else None
        )
        row.micronutrients_status = day_line.micronutrients_status
        row.is_estimated = day_line.is_estimated
        row.entries = {
            str(entry_id): nutrient_total_line_to_dict(line)
            for entry_id, line in total.entries.items()
        }
        row.updated_at = datetime.now(timezone.utc)
        await self._session.flush()

    async def find_date_for_entry(self, user_id: uuid.UUID, entry_id: uuid.UUID) -> date | None:
        stmt = select(DailyNutritionTotalModel.total_date).where(
            DailyNutritionTotalModel.user_id == user_id,
            DailyNutritionTotalModel.entries.has_key(str(entry_id)),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
