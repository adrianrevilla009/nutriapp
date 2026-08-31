"""PostgresEntitlementCacheRepository -- implements
EntitlementCacheRepositoryPort. `get()` returns `None` for a genuine
cache-miss (no row yet), distinguishable from an explicit `False` row --
this is what lets the application layer decide when to fall back to the
synchronous `EntitlementCheckPort`. Mirrors recipe-service's identical
adapter verbatim."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import EntitlementCacheModel


class PostgresEntitlementCacheRepository:
    """Implements domain.ports.entitlement_cache_repository_port.EntitlementCacheRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: uuid.UUID) -> bool | None:
        row = await self._session.get(EntitlementCacheModel, user_id)
        return row.entitled if row is not None else None

    async def upsert(self, user_id: uuid.UUID, entitled: bool, updated_at: datetime) -> None:
        row = await self._session.get(EntitlementCacheModel, user_id)
        if row is None:
            row = EntitlementCacheModel(user_id=user_id)
            self._session.add(row)
        row.entitled = entitled
        row.updated_at = updated_at
        await self._session.flush()
