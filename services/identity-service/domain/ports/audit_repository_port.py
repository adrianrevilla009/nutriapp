from __future__ import annotations

from typing import Protocol

from domain.entities.audit_record import AuditRecord


class AuditRepositoryPort(Protocol):
    async def record(self, entry: AuditRecord) -> None: ...
