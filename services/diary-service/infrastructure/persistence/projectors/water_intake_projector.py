"""PostgresWaterIntakeProjector -- writes AND reads water_intake_view."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain.events.base import DomainEvent
from infrastructure.persistence.models import WaterIntakeViewModel


class PostgresWaterIntakeProjector:
    """Implements WaterIntakeReadPort and the write side used by
    diary_event_projector_consumer / scripts/rebuild_read_models.py."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def apply(self, event: DomainEvent) -> None:
        if event.event_type == "WaterIntakeLogged":
            await self._apply_logged(event)
        elif event.event_type == "WaterIntakeRemoved":
            await self._apply_removed(event)

    async def _apply_logged(self, event: DomainEvent) -> None:
        stmt = (
            pg_insert(WaterIntakeViewModel)
            .values(
                intake_id=uuid.UUID(event.payload["intake_id"]),
                user_id=uuid.UUID(event.payload["user_id"]),
                amount_ml=float(event.payload["amount_ml"]),
                occurred_at=datetime.fromisoformat(event.payload["occurred_at"]),
                removed=False,
                updated_at=event.occurred_at,
            )
            .on_conflict_do_nothing(index_elements=["intake_id"])
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def _apply_removed(self, event: DomainEvent) -> None:
        row = await self._session.get(WaterIntakeViewModel, uuid.UUID(event.payload["intake_id"]))
        if row is None:
            return
        row.removed = True
        row.updated_at = event.occurred_at
        await self._session.flush()

    async def list_intake(
        self, user_id: uuid.UUID, from_date: date | None, to_date: date | None
    ) -> list[dict[str, Any]]:
        conditions = [WaterIntakeViewModel.user_id == user_id]
        if from_date is not None:
            conditions.append(
                WaterIntakeViewModel.occurred_at >= datetime.combine(from_date, datetime.min.time())
            )
        if to_date is not None:
            conditions.append(
                WaterIntakeViewModel.occurred_at <= datetime.combine(to_date, datetime.max.time())
            )
        stmt = (
            select(WaterIntakeViewModel)
            .where(and_(*conditions))
            .order_by(WaterIntakeViewModel.occurred_at.asc())
        )
        result = await self._session.execute(stmt)
        return [
            {
                "intake_id": row.intake_id,
                "user_id": row.user_id,
                "amount_ml": row.amount_ml,
                "occurred_at": row.occurred_at,
                "removed": row.removed,
            }
            for row in result.scalars()
        ]

    async def get_daily_total_ml(self, user_id: uuid.UUID, summary_date: date) -> float:
        start = datetime.combine(summary_date, datetime.min.time())
        end = datetime.combine(summary_date, datetime.max.time())
        stmt = select(WaterIntakeViewModel).where(
            WaterIntakeViewModel.user_id == user_id,
            WaterIntakeViewModel.removed.is_(False),
            WaterIntakeViewModel.occurred_at >= start,
            WaterIntakeViewModel.occurred_at <= end,
        )
        result = await self._session.execute(stmt)
        return sum(r.amount_ml for r in result.scalars())
