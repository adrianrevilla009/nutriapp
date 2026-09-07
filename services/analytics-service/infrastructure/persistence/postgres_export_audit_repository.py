"""Implements domain.ports.export_audit_repository_port.ExportAuditRepositoryPort --
immutable, append-only (CLAUDE.md section 2.8). `record` always inserts a
new row, never upserts -- every export is its own audit fact."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

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
    ) -> None:
        self._session.add(
            ExportAuditLogModel(
                user_id=user_id,
                report_type=report_type,
                requested_at=requested_at,
                export_format=export_format,
                start_date=start_date,
                end_date=end_date,
                row_count=row_count,
            )
        )
        await self._session.flush()
