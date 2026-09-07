"""Implements domain.ports.analytics_signals_repository_port.AnalyticsSignalsRepositoryPort."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.value_objects.retrieved_record import RetrievedRecord
from infrastructure.persistence.models import AnalyticsSignalModel


class PostgresAnalyticsSignalsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_deficiency_signal(
        self, user_id: uuid.UUID, signal: str, summary: str, disclaimer: str
    ) -> None:
        key = {"user_id": user_id, "signal": signal}
        row = await self._session.get(AnalyticsSignalModel, key)
        if row is None:
            row = AnalyticsSignalModel(
                user_id=user_id, signal=signal, summary=summary, disclaimer=disclaimer
            )
            self._session.add(row)
        else:
            row.summary = summary
            row.disclaimer = disclaimer  # verbatim, never re-worded
        await self._session.flush()

    async def recent_for_user(self, user_id: uuid.UUID, limit: int = 10) -> list[RetrievedRecord]:
        stmt = (
            select(AnalyticsSignalModel).where(AnalyticsSignalModel.user_id == user_id).limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            RetrievedRecord(
                record_id=f"{row.user_id}:{row.signal}",
                source="analytics",
                content=f"{row.summary} {row.disclaimer}",
            )
            for row in rows
        ]
