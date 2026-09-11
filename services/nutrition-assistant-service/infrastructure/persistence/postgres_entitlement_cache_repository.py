"""Implements domain.ports.entitlement_cache_repository_port.EntitlementCacheRepositoryPort.

`upsert` persists the caller-supplied `occurred_at` (the event's own
`granted_at`/`revoked_at`) into `updated_at`, never a fresh wall-clock
timestamp -- implementation plan addendum, 2026-09-08."""

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
        return None if row is None else row.entitled

    async def upsert(self, user_id: uuid.UUID, entitled: bool, occurred_at: datetime) -> None:
        row = await self._session.get(EntitlementCacheModel, user_id)
        if row is None:
            self._session.add(
                EntitlementCacheModel(user_id=user_id, entitled=entitled, updated_at=occurred_at)
            )
        else:
            row.entitled = entitled
            row.updated_at = occurred_at
        await self._session.flush()
