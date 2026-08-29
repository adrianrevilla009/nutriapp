"""PostgresEntitlementRevocationScheduleRepository -- implements
EntitlementRevocationScheduleRepositoryPort. Backs the deferred-
`EntitlementRevoked` mechanism (implementation plan section 1.5)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.ports.entitlement_revocation_schedule_repository_port import RevocationScheduleEntry
from infrastructure.persistence.models import EntitlementRevocationScheduleModel


def _to_domain(row: EntitlementRevocationScheduleModel) -> RevocationScheduleEntry:
    return RevocationScheduleEntry(
        user_id=row.user_id, revoke_at=row.revoke_at, processed=row.processed
    )


class PostgresEntitlementRevocationScheduleRepository:
    """Implements
    domain.ports.entitlement_revocation_schedule_repository_port.EntitlementRevocationScheduleRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_pending(self, user_id: uuid.UUID, revoke_at: datetime) -> None:
        row = await self._session.get(EntitlementRevocationScheduleModel, user_id)
        if row is not None and row.processed:
            # Already finalized -- never un-process an already-processed
            # row (idempotency: a replayed customer.subscription.deleted
            # for a user whose revocation already ran must not resurrect it).
            return
        if row is None:
            row = EntitlementRevocationScheduleModel(user_id=user_id, processed=False)
            self._session.add(row)
        row.revoke_at = revoke_at
        row.processed = False
        await self._session.flush()

    async def list_due(self, now: datetime, limit: int = 100) -> list[RevocationScheduleEntry]:
        stmt = (
            select(EntitlementRevocationScheduleModel)
            .where(EntitlementRevocationScheduleModel.processed.is_(False))
            .where(EntitlementRevocationScheduleModel.revoke_at <= now)
            .order_by(EntitlementRevocationScheduleModel.revoke_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [_to_domain(row) for row in result.scalars()]

    async def mark_processed(self, user_id: uuid.UUID) -> None:
        row = await self._session.get(EntitlementRevocationScheduleModel, user_id)
        if row is not None:
            row.processed = True
            await self._session.flush()
