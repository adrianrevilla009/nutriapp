"""RevocationScanWorker -- the periodic in-service worker (implementation
plan section 1.5/9's "reuse the periodic-worker shape already established
by notification-service's reminder_scan_worker.py" instruction). Not a
message consumer -- a plain polling loop invoking
ProcessDueRevocationsHandler, same run_forever shape as every other
service's OutboxRelayWorker / notification-service's ReminderScanWorker."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.process_due_revocations import (
    ProcessDueRevocationsCommand,
    ProcessDueRevocationsHandler,
)
from infrastructure.persistence.postgres_entitlement_revocation_schedule_repository import (
    PostgresEntitlementRevocationScheduleRepository,
)
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository

logger = structlog.get_logger()

DEFAULT_SCAN_INTERVAL_SECONDS = 60.0


class RevocationScanWorker:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        scan_interval_seconds: float = DEFAULT_SCAN_INTERVAL_SECONDS,
    ) -> None:
        self._session_factory = session_factory
        self._scan_interval_seconds = scan_interval_seconds

    async def scan_once(self) -> int:
        # Every repository is built from the SAME session (one transaction
        # per scan tick), mirroring OutboxRelayWorker's convention.
        async with self._session_factory() as session:
            revocation_schedule = PostgresEntitlementRevocationScheduleRepository(session)
            outbox = PostgresOutboxRepository(session)
            handler = ProcessDueRevocationsHandler(revocation_schedule, outbox)
            processed_count = await handler.handle(
                ProcessDueRevocationsCommand(correlation_id=str(uuid.uuid4()))
            )
            await session.commit()
        return processed_count

    async def run_forever(self) -> None:
        while True:
            try:
                await self.scan_once()
            except Exception:
                logger.exception("revocation_scan_iteration_failed")
            await asyncio.sleep(self._scan_interval_seconds)
