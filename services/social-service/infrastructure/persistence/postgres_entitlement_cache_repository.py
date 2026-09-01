"""social-service's local read-through cache of billing-service's
entitlement flag. The one thing that matters for callers
(`application/entitlement_check.py`): `get()` returns `None` for a
genuine cache-miss (no row written yet), which is distinguishable from an
explicit, previously-cached `False` -- that distinction is exactly what
lets `is_user_entitled` decide whether it needs to fall back to the
synchronous `EntitlementCheckPort` at all."""

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
