"""ExportAuditRepositoryPort -- immutable, append-only audit trail for
every successful data export/report generation (CLAUDE.md section 2.8
explicitly names "data exports" as mandatory audit-trail scope).
`record` is called exactly once per successful export, including on a
repeated identical request -- never deduplicated like event-consumption
idempotency (test-plan section 2's explicit "every export logs" rule).
First-cut schema (implementation plan section 9 addendum, resolution 7)
-- flagged for `security-agent` review before prod promotion."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Protocol


class ExportAuditRepositoryPort(Protocol):
    async def record(
        self,
        user_id: uuid.UUID,
        report_type: str,
        requested_at: datetime,
        export_format: str,
        start_date: date,
        end_date: date,
        row_count: int,
    ) -> None: ...
