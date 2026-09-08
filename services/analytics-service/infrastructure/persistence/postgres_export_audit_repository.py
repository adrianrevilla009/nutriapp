"""Implements domain.ports.export_audit_repository_port.ExportAuditRepositoryPort --
immutable, append-only (CLAUDE.md section 2.8, docs/observability-and-audit.md
section 4.3). `record` always inserts a new row, never upserts -- every
export request (success or rejection) is its own audit fact.

Commits its own session independently of any caller-managed transaction
(identity-service's/profile-service's `PostgresAuditRepository` precedent,
verbatim) -- an audit record must survive even if the request that
triggered it is subsequently rejected/rolled back. In production this
repository is always constructed over `Container.new_audit_session()`,
whose underlying connection runs as `AUDIT_WRITER_ROLE` (INSERT/SELECT
only, `UPDATE`/`DELETE` revoked at the Postgres level -- see
`infrastructure/composition_root.py` and
migrations/versions/0002_export_audit_log_compliance.py)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from domain.value_objects.export_outcome import ExportOutcome
from infrastructure.persistence.models import ExportAuditLogModel


class PostgresExportAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        user_id: uuid.UUID,
        report_type: str,
        requested_at: datetime,
        export_format: str,
        start_date: date,
        end_date: date,
        row_count: int,
        outcome: ExportOutcome,
        actor_id: uuid.UUID,
        action: str,
        target_type: str,
        target_id: str,
        correlation_id: str,
        rejection_reason: str | None = None,
    ) -> None:
        metadata: dict[str, object] = {}
        if rejection_reason is not None:
            metadata["rejection_reason"] = rejection_reason

        self._session.add(
            ExportAuditLogModel(
                user_id=user_id,
                report_type=report_type,
                requested_at=requested_at,
                export_format=export_format,
                start_date=start_date,
                end_date=end_date,
                row_count=row_count,
                outcome=outcome.value,
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                correlation_id=correlation_id,
                audit_metadata=metadata,
            )
        )
        await self._session.commit()
