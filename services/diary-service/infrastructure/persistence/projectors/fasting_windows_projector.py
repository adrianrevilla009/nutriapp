"""PostgresFastingWindowsProjector -- writes AND reads fasting_windows_view."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain.events.base import DomainEvent
from infrastructure.persistence.models import FastingWindowViewModel


class PostgresFastingWindowsProjector:
    """Implements FastingWindowsReadPort and the write side used by
    diary_event_projector_consumer / scripts/rebuild_read_models.py."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def apply(self, event: DomainEvent) -> None:
        if event.event_type == "FastingWindowStarted":
            await self._apply_started(event)
        elif event.event_type == "FastingWindowEnded":
            await self._apply_ended(event)

    async def _apply_started(self, event: DomainEvent) -> None:
        stmt = (
            pg_insert(FastingWindowViewModel)
            .values(
                window_id=uuid.UUID(event.payload["window_id"]),
                user_id=uuid.UUID(event.payload["user_id"]),
                started_at=datetime.fromisoformat(event.payload["started_at"]),
                ended_at=None,
                updated_at=event.occurred_at,
            )
            .on_conflict_do_nothing(index_elements=["window_id"])
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def _apply_ended(self, event: DomainEvent) -> None:
        row = await self._session.get(FastingWindowViewModel, uuid.UUID(event.payload["window_id"]))
        if row is None:
            return
        row.ended_at = datetime.fromisoformat(event.payload["ended_at"])
        row.updated_at = event.occurred_at
        await self._session.flush()

    async def get_history(self, user_id: uuid.UUID, limit: int = 50) -> list[dict[str, Any]]:
        stmt = (
            select(FastingWindowViewModel)
            .where(FastingWindowViewModel.user_id == user_id)
            .order_by(FastingWindowViewModel.started_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [
            {
                "window_id": row.window_id,
                "user_id": row.user_id,
                "started_at": row.started_at,
                "ended_at": row.ended_at,
            }
            for row in result.scalars()
        ]

    async def count_ended_on(self, user_id: uuid.UUID, summary_date: date) -> int:
        start = datetime.combine(summary_date, datetime.min.time())
        end = datetime.combine(summary_date, datetime.max.time())
        stmt = select(FastingWindowViewModel).where(
            FastingWindowViewModel.user_id == user_id,
            FastingWindowViewModel.ended_at.is_not(None),
            FastingWindowViewModel.ended_at >= start,
            FastingWindowViewModel.ended_at <= end,
        )
        result = await self._session.execute(stmt)
        return len(list(result.scalars()))
