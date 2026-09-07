"""Implements domain.ports.chat_audit_repository_port.ChatAuditRepositoryPort.
Write-only -- no read/list method, per implementation plan section 9
resolution 6 (traceability, not a resumable-chat feature)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import ChatAuditLogModel


class PostgresChatAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        user_id: uuid.UUID,
        query: str,
        retrieved_record_ids: list[str],
        prompt_template_version: str,
        had_sufficient_context: bool,
        disclaimer_included: bool,
    ) -> None:
        self._session.add(
            ChatAuditLogModel(
                audit_id=uuid.uuid4(),
                user_id=user_id,
                query=query,
                retrieved_record_ids=retrieved_record_ids,
                prompt_template_version=prompt_template_version,
                had_sufficient_context=had_sufficient_context,
                disclaimer_included=disclaimer_included,
                recorded_at=datetime.now(UTC),
            )
        )
        await self._session.flush()
