"""ReminderScanWorker -- the periodic in-service worker (implementation
plan section 1/9.1's "local reminder_schedule projection + an in-service
scheduler" design, resolved by architecture-agent specifically to avoid a
new synchronous call into diary-service). Not a message consumer -- a
plain polling loop invoking ScanAndSendDueRemindersHandler, same
run_forever shape as every other service's OutboxRelayWorker."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.scan_and_send_due_reminders import ScanAndSendDueRemindersHandler
from domain.ports.push_provider_port import PushProviderPort
from domain.ports.template_renderer_port import TemplateRendererPort
from infrastructure.persistence.postgres_delivery_log_repository import (
    PostgresDeliveryLogRepository,
)
from infrastructure.persistence.postgres_preferences_repository import (
    PostgresPreferencesRepository,
)
from infrastructure.persistence.postgres_reminder_schedule_repository import (
    PostgresReminderScheduleRepository,
)
from infrastructure.persistence.postgres_suppression_repository import (
    PostgresSuppressionRepository,
)

logger = structlog.get_logger()

DEFAULT_SCAN_INTERVAL_SECONDS = 60.0


class ReminderScanWorker:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        push_provider: PushProviderPort,
        template_renderer: TemplateRendererPort,
        scan_interval_seconds: float = DEFAULT_SCAN_INTERVAL_SECONDS,
    ) -> None:
        self._session_factory = session_factory
        self._push_provider = push_provider
        self._template_renderer = template_renderer
        self._scan_interval_seconds = scan_interval_seconds

    async def scan_once(self, now: datetime | None = None) -> None:
        # Every repository is built from the SAME session (one transaction
        # per scan tick), mirroring OutboxRelayWorker's convention -- the
        # preferences repository is no exception, so it is never
        # constructed from a stale, long-lived session held across ticks.
        # `now` is an explicit passthrough (defaults to the handler's own
        # real-clock now_fn) so tests can pin the scan instant instead of
        # racing the real wall clock.
        async with self._session_factory() as session:
            reminder_schedule = PostgresReminderScheduleRepository(session)
            preferences = PostgresPreferencesRepository(session)
            suppression = PostgresSuppressionRepository(session)
            delivery_log = PostgresDeliveryLogRepository(session)
            handler = ScanAndSendDueRemindersHandler(
                reminder_schedule,
                preferences,
                self._push_provider,
                suppression,
                self._template_renderer,
                delivery_log,
            )
            await handler.handle(now)
            await session.commit()

    async def run_forever(self) -> None:
        while True:
            try:
                await self.scan_once()
            except Exception:
                logger.exception("reminder_scan_iteration_failed")
            await asyncio.sleep(self._scan_interval_seconds)
