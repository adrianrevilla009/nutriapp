"""ProcessDueRevocationsHandler -- the scheduled-worker use case backing
`revocation_scan_worker.py` (implementation plan section 1.5): scans
`entitlement_revocation_schedule` for due, unprocessed rows and publishes
`EntitlementRevoked` for each -- this is the ONLY place `EntitlementRevoked`
is ever published, never synchronously from the cancellation webhook
handler."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from domain.events.entitlement_revoked import build_entitlement_revoked_event
from domain.ports.entitlement_revocation_schedule_repository_port import (
    EntitlementRevocationScheduleRepositoryPort,
)
from domain.ports.outbox_repository_port import OutboxRepositoryPort


@dataclass(frozen=True, slots=True)
class ProcessDueRevocationsCommand:
    correlation_id: str


class ProcessDueRevocationsHandler:
    def __init__(
        self,
        revocation_schedule: EntitlementRevocationScheduleRepositoryPort,
        outbox: OutboxRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._revocation_schedule = revocation_schedule
        self._outbox = outbox
        self._now_fn = now_fn

    async def handle(self, command: ProcessDueRevocationsCommand) -> int:
        now = self._now_fn()
        due = await self._revocation_schedule.list_due(now)
        for entry in due:
            event = build_entitlement_revoked_event(
                user_id=entry.user_id, correlation_id=command.correlation_id
            )
            await self._outbox.enqueue(event)
            await self._revocation_schedule.mark_processed(entry.user_id)
        return len(due)
