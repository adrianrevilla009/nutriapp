"""ExportAuditRepositoryPort -- immutable, append-only audit trail for
every data export/report REQUEST (CLAUDE.md section 2.8 and
docs/observability-and-audit.md section 4.1, which mandates auditing
"data export requests" -- not just successful ones). `record` is called
exactly once per call to `GetReportHandler.handle`, success or rejection,
including on a repeated identical request -- never deduplicated like
event-consumption idempotency (test-plan section 2's explicit "every
export logs" rule).

Schema fields mirror docs/observability-and-audit.md section 4.2's
mandatory audit record shape (`audit_id`/`occurred_at` are represented by
this table's pre-existing `export_id`/`requested_at` columns; the rest --
`outcome`, `actor_id`, `action`, `target_type`, `target_id`,
`correlation_id` -- were the concrete schema-drift gap a security review
found before this port was extended). Fixed by the same review that
flagged the append-only DB-role enforcement gap in
migrations/versions/0002_export_audit_log_compliance.py."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Protocol

from domain.value_objects.export_outcome import ExportOutcome


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
        outcome: ExportOutcome,
        actor_id: uuid.UUID,
        action: str,
        target_type: str,
        target_id: str,
        correlation_id: str,
        rejection_reason: str | None = None,
    ) -> None: ...
