"""Implements domain.ports.entitlement_cache_repository_port.EntitlementCacheRepositoryPort --
own local copy per CLAUDE.md section 2.5, structurally identical to
recipe-service's/social-service's own repository of the same name."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import EntitlementCacheModel


class PostgresEntitlementCacheRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: uuid.UUID) -> bool | None:
        row = await self._session.get(EntitlementCacheModel, user_id)
        if row is None:
            return None
        return row.entitled

    async def upsert(self, user_id: uuid.UUID, entitled: bool, updated_at: datetime) -> None:
        row = await self._session.get(EntitlementCacheModel, user_id)
        if row is None:
            row = EntitlementCacheModel(user_id=user_id)
            self._session.add(row)

        row.entitled = entitled
        row.updated_at = updated_at
        await self._session.flush()
