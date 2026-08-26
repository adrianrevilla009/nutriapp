"""PostgresFoodEntriesProjector -- writes AND reads food_entries_view.

apply() is idempotent under replay: FoodEntryLogged upserts (INSERT ...
ON CONFLICT DO NOTHING on entry_id), so redelivery or a rebuild replay
that isn't preceded by a truncate never duplicates a row. Corrected/
Deleted events look up the existing row and update it in place (this is
projection-table mutation, not historical-event mutation -- the
diary_events row for FoodEntryLogged is never touched, per CLAUDE.md's
"never mutate historical events").
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain.events.base import DomainEvent
from infrastructure.persistence.models import FoodEntryViewModel


class PostgresFoodEntriesProjector:
    """Implements FoodEntriesReadPort and the write side used by
    diary_event_projector_consumer / scripts/rebuild_read_models.py."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def apply(self, event: DomainEvent) -> None:
        if event.event_type == "FoodEntryLogged":
            await self._apply_logged(event)
        elif event.event_type == "FoodEntryCorrected":
            await self._apply_corrected(event)
        elif event.event_type == "FoodEntryDeleted":
            await self._apply_deleted(event)

    async def _apply_logged(self, event: DomainEvent) -> None:
        source = event.payload["source"]
        macros = source["snapshot"]["macros_per_unit"]
        stmt = (
            pg_insert(FoodEntryViewModel)
            .values(
                entry_id=uuid.UUID(event.payload["entry_id"]),
                user_id=uuid.UUID(event.payload["user_id"]),
                source=source,
                meal_slot=event.payload["meal_slot"],
                occurred_at=datetime.fromisoformat(event.payload["occurred_at"]),
                calories_kcal=float(macros["calories_kcal"]),
                protein_g=float(macros["protein_g"]),
                carbs_g=float(macros["carbs_g"]),
                fat_g=float(macros["fat_g"]),
                deleted=False,
                updated_at=event.occurred_at,
            )
            .on_conflict_do_nothing(index_elements=["entry_id"])
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def _apply_corrected(self, event: DomainEvent) -> None:
        row = await self._session.get(FoodEntryViewModel, uuid.UUID(event.payload["entry_id"]))
        if row is None:
            return
        source = event.payload["source"]
        macros = source["snapshot"]["macros_per_unit"]
        row.source = source
        row.meal_slot = event.payload["meal_slot"]
        row.occurred_at = datetime.fromisoformat(event.payload["occurred_at"])
        row.calories_kcal = float(macros["calories_kcal"])
        row.protein_g = float(macros["protein_g"])
        row.carbs_g = float(macros["carbs_g"])
        row.fat_g = float(macros["fat_g"])
        row.updated_at = event.occurred_at
        await self._session.flush()

    async def _apply_deleted(self, event: DomainEvent) -> None:
        row = await self._session.get(FoodEntryViewModel, uuid.UUID(event.payload["entry_id"]))
        if row is None:
            return
        row.deleted = True
        row.updated_at = event.occurred_at
        await self._session.flush()

    async def list_entries(
        self, user_id: uuid.UUID, from_date: date | None, to_date: date | None
    ) -> list[dict[str, Any]]:
        conditions = [FoodEntryViewModel.user_id == user_id]
        if from_date is not None:
            conditions.append(
                FoodEntryViewModel.occurred_at >= datetime.combine(from_date, datetime.min.time())
            )
        if to_date is not None:
            conditions.append(
                FoodEntryViewModel.occurred_at <= datetime.combine(to_date, datetime.max.time())
            )
        stmt = (
            select(FoodEntryViewModel)
            .where(and_(*conditions))
            .order_by(FoodEntryViewModel.occurred_at.asc())
        )
        result = await self._session.execute(stmt)
        return [
            {
                "entry_id": row.entry_id,
                "user_id": row.user_id,
                "source": row.source,
                "meal_slot": row.meal_slot,
                "occurred_at": row.occurred_at,
                "deleted": row.deleted,
            }
            for row in result.scalars()
        ]

    async def get_daily_totals(self, user_id: uuid.UUID, summary_date: date) -> dict[str, float]:
        """Used by PostgresDailySummaryProjector to recompute the daily
        summary's food-derived fields from this (already up to date)
        projection -- avoids duplicating macro-aggregation logic."""
        start = datetime.combine(summary_date, datetime.min.time())
        end = datetime.combine(summary_date, datetime.max.time())
        stmt = select(FoodEntryViewModel).where(
            FoodEntryViewModel.user_id == user_id,
            FoodEntryViewModel.deleted.is_(False),
            FoodEntryViewModel.occurred_at >= start,
            FoodEntryViewModel.occurred_at <= end,
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars())
        return {
            "total_calories_kcal": sum(r.calories_kcal for r in rows),
            "total_protein_g": sum(r.protein_g for r in rows),
            "total_carbs_g": sum(r.carbs_g for r in rows),
            "total_fat_g": sum(r.fat_g for r in rows),
        }
