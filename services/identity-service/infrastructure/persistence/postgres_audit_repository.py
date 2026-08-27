"""PostgresAuditRepository — implements AuditRepositoryPort.

Uses a dedicated session bound to a DB role granted INSERT-only on
`audit_log` (see migrations/versions/0001_create_identity_tables.py and
observability-audit SKILL.md). Commits independently of the caller's main
transaction so an audit record survives even if the triggering operation
is subsequently rolled back by the caller.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.audit_record import AuditRecord
from infrastructure.persistence.models import AuditLogModel


class PostgresAuditRepository:
    """Implements domain.ports.audit_repository_port.AuditRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, entry: AuditRecord) -> None:
        row = AuditLogModel(
            audit_id=entry.audit_id,
            occurred_at=entry.occurred_at,
            actor_id=entry.actor_id,
            action=entry.action,
            target_type=entry.target_type,
            target_id=entry.target_id,
            outcome=entry.outcome,
            audit_metadata=entry.metadata,
            correlation_id=entry.correlation_id,
        )
        self._session.add(row)
        await self._session.commit()
