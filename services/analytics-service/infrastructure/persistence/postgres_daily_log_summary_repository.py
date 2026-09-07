"""Implements domain.ports.daily_log_summary_repository_port.DailyLogSummaryRepositoryPort.

Owns two internal ledger tables (`food_entry_contributions`,
`water_intake_contributions`) purely to make `correct_food_entry`/
`remove_food_entry`/`remove_water_intake` exact -- see the port's
docstring for why. Callers never see the ledger."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.services.trend_calculator import DailyMacroTotals
from infrastructure.persistence.models import (
    DailyLogSummaryModel,
    FoodEntryContributionModel,
    WaterIntakeContributionModel,
)


class PostgresDailyLogSummaryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _get_or_create_day(self, user_id: uuid.UUID, on_date: date) -> DailyLogSummaryModel:
        row = await self._session.get(
            DailyLogSummaryModel, {"user_id": user_id, "on_date": on_date}
        )
        if row is None:
            row = DailyLogSummaryModel(
                user_id=user_id,
                on_date=on_date,
                calories_kcal=0.0,
                protein_g=0.0,
                carbs_g=0.0,
                fat_g=0.0,
                water_ml=0.0,
                entries_logged_count=0,
            )
            self._session.add(row)
        return row

    async def _apply_delta(
        self,
        user_id: uuid.UUID,
        on_date: date,
        *,
        calories_kcal: float = 0.0,
        protein_g: float = 0.0,
        carbs_g: float = 0.0,
        fat_g: float = 0.0,
        water_ml: float = 0.0,
        entries_logged_delta: int = 0,
    ) -> None:
        row = await self._get_or_create_day(user_id, on_date)
        row.calories_kcal += calories_kcal
        row.protein_g += protein_g
        row.carbs_g += carbs_g
        row.fat_g += fat_g
        row.water_ml += water_ml
        row.entries_logged_count += entries_logged_delta
        await self._session.flush()

    async def apply_food_entry(
        self,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
        on_date: date,
        calories_kcal: float,
        protein_g: float,
        carbs_g: float,
        fat_g: float,
    ) -> None:
        existing = await self._session.get(FoodEntryContributionModel, entry_id)
        if existing is not None:
            return  # already applied (defensive -- callers already idempotency-guard by event_id)

        self._session.add(
            FoodEntryContributionModel(
                entry_id=entry_id,
                user_id=user_id,
                on_date=on_date,
                calories_kcal=calories_kcal,
                protein_g=protein_g,
                carbs_g=carbs_g,
                fat_g=fat_g,
            )
        )
        await self._apply_delta(
            user_id,
            on_date,
            calories_kcal=calories_kcal,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            entries_logged_delta=1,
        )

    async def correct_food_entry(
        self,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
        on_date: date,
        calories_kcal: float,
        protein_g: float,
        carbs_g: float,
        fat_g: float,
    ) -> None:
        previous = await self._session.get(FoodEntryContributionModel, entry_id)
        if previous is not None:
            await self._apply_delta(
                previous.user_id,
                previous.on_date,
                calories_kcal=-previous.calories_kcal,
                protein_g=-previous.protein_g,
                carbs_g=-previous.carbs_g,
                fat_g=-previous.fat_g,
                entries_logged_delta=-1,
            )
            previous.on_date = on_date
            previous.calories_kcal = calories_kcal
            previous.protein_g = protein_g
            previous.carbs_g = carbs_g
            previous.fat_g = fat_g
        else:
            self._session.add(
                FoodEntryContributionModel(
                    entry_id=entry_id,
                    user_id=user_id,
                    on_date=on_date,
                    calories_kcal=calories_kcal,
                    protein_g=protein_g,
                    carbs_g=carbs_g,
                    fat_g=fat_g,
                )
            )

        await self._apply_delta(
            user_id,
            on_date,
            calories_kcal=calories_kcal,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            entries_logged_delta=1,
        )

    async def remove_food_entry(self, entry_id: uuid.UUID) -> None:
        row = await self._session.get(FoodEntryContributionModel, entry_id)
        if row is None:
            return  # already removed/never applied -- idempotent no-op

        await self._apply_delta(
            row.user_id,
            row.on_date,
            calories_kcal=-row.calories_kcal,
            protein_g=-row.protein_g,
            carbs_g=-row.carbs_g,
            fat_g=-row.fat_g,
            entries_logged_delta=-1,
        )
        await self._session.delete(row)
        await self._session.flush()

    async def apply_water_intake(
        self, intake_id: uuid.UUID, user_id: uuid.UUID, on_date: date, amount_ml: float
    ) -> None:
        existing = await self._session.get(WaterIntakeContributionModel, intake_id)
        if existing is not None:
            return

        self._session.add(
            WaterIntakeContributionModel(
                intake_id=intake_id, user_id=user_id, on_date=on_date, amount_ml=amount_ml
            )
        )
        await self._apply_delta(user_id, on_date, water_ml=amount_ml)

    async def remove_water_intake(self, intake_id: uuid.UUID) -> None:
        row = await self._session.get(WaterIntakeContributionModel, intake_id)
        if row is None:
            return

        await self._apply_delta(row.user_id, row.on_date, water_ml=-row.amount_ml)
        await self._session.delete(row)
        await self._session.flush()

    async def list_window(
        self, user_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[DailyMacroTotals]:
        stmt = (
            select(DailyLogSummaryModel)
            .where(
                DailyLogSummaryModel.user_id == user_id,
                DailyLogSummaryModel.on_date >= start_date,
                DailyLogSummaryModel.on_date <= end_date,
            )
            .order_by(DailyLogSummaryModel.on_date.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            DailyMacroTotals(
                on_date=row.on_date,
                calories_kcal=row.calories_kcal,
                protein_g=row.protein_g,
                carbs_g=row.carbs_g,
                fat_g=row.fat_g,
                water_ml=row.water_ml,
            )
            for row in rows
        ]
