"""Implements domain.ports.anomaly_alerts_repository_port.AnomalyAlertsRepositoryPort --
append-only (never updates/deletes an existing row), doubling as the
14-day cooldown dedup guard."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import AnomalyAlertModel


class PostgresAnomalyAlertsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def most_recent_detection_at(self, user_id: uuid.UUID, signal: str) -> datetime | None:
        stmt = (
            select(AnomalyAlertModel.detected_at)
            .where(AnomalyAlertModel.user_id == user_id, AnomalyAlertModel.signal == signal)
            .order_by(AnomalyAlertModel.detected_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def record_detection(
        self,
        user_id: uuid.UUID,
        signal: str,
        window_days: int,
        value: float,
        detected_at: datetime,
    ) -> None:
        self._session.add(
            AnomalyAlertModel(
                user_id=user_id,
                signal=signal,
                window_days=window_days,
                value=value,
                detected_at=detected_at,
            )
        )
        await self._session.flush()
