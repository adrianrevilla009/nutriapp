"""Implements domain.ports.entitlement_cache_repository_port.EntitlementCacheRepositoryPort."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import EntitlementCacheModel


class PostgresEntitlementCacheRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: uuid.UUID) -> bool | None:
        row = await self._session.get(EntitlementCacheModel, user_id)
        return None if row is None else row.entitled

    async def set(self, user_id: uuid.UUID, entitled: bool) -> None:
        row = await self._session.get(EntitlementCacheModel, user_id)
        now = datetime.now(UTC)
        if row is None:
            self._session.add(
                EntitlementCacheModel(user_id=user_id, entitled=entitled, updated_at=now)
            )
        else:
            row.entitled = entitled
            row.updated_at = now
        await self._session.flush()
