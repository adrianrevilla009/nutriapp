"""PostgresMealPlanProjector -- writes AND reads meal_plan_view."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain.events.base import DomainEvent
from infrastructure.persistence.models import MealPlanViewModel


class PostgresMealPlanProjector:
    """Implements MealPlanReadPort and the write side used by
    diary_event_projector_consumer / scripts/rebuild_read_models.py."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def apply(self, event: DomainEvent) -> None:
        if event.event_type == "MealPlanned":
            await self._apply_planned(event)
        elif event.event_type == "MealPlanUpdated":
            await self._apply_updated(event)
        elif event.event_type == "MealPlanRemoved":
            await self._apply_removed(event)

    async def _apply_planned(self, event: DomainEvent) -> None:
        stmt = (
            pg_insert(MealPlanViewModel)
            .values(
                plan_entry_id=uuid.UUID(event.payload["plan_entry_id"]),
                user_id=uuid.UUID(event.payload["user_id"]),
                source=event.payload["source"],
                meal_slot=event.payload["meal_slot"],
                planned_for=datetime.fromisoformat(event.payload["planned_for"]),
                removed=False,
                updated_at=event.occurred_at,
            )
            .on_conflict_do_nothing(index_elements=["plan_entry_id"])
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def _apply_updated(self, event: DomainEvent) -> None:
        row = await self._session.get(MealPlanViewModel, uuid.UUID(event.payload["plan_entry_id"]))
        if row is None:
            return
        row.source = event.payload["source"]
        row.meal_slot = event.payload["meal_slot"]
        row.planned_for = datetime.fromisoformat(event.payload["planned_for"])
        row.updated_at = event.occurred_at
        await self._session.flush()

    async def _apply_removed(self, event: DomainEvent) -> None:
        row = await self._session.get(MealPlanViewModel, uuid.UUID(event.payload["plan_entry_id"]))
        if row is None:
            return
        row.removed = True
        row.updated_at = event.occurred_at
        await self._session.flush()

    async def get_calendar(
        self, user_id: uuid.UUID, from_date: date, to_date: date
    ) -> list[dict[str, Any]]:
        conditions = [
            MealPlanViewModel.user_id == user_id,
            MealPlanViewModel.planned_for >= datetime.combine(from_date, datetime.min.time()),
            MealPlanViewModel.planned_for <= datetime.combine(to_date, datetime.max.time()),
        ]
        stmt = (
            select(MealPlanViewModel)
            .where(and_(*conditions))
            .order_by(MealPlanViewModel.planned_for.asc())
        )
        result = await self._session.execute(stmt)
        return [
            {
                "plan_entry_id": row.plan_entry_id,
                "user_id": row.user_id,
                "source": row.source,
                "meal_slot": row.meal_slot,
                "planned_for": row.planned_for,
                "removed": row.removed,
            }
            for row in result.scalars()
        ]
