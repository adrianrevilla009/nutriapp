"""PendingPushDispatchScanWorker -- the periodic in-service worker for
`pending_push_dispatch` rows, mirroring reminder_scan_worker.py's
run_forever shape exactly. Not a message consumer -- a plain polling loop
invoking ScanAndSendPendingPushDispatchesHandler."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.scan_and_send_pending_push_dispatches import (
    ScanAndSendPendingPushDispatchesHandler,
)
from domain.ports.push_provider_port import PushProviderPort
from domain.ports.template_renderer_port import TemplateRendererPort
from infrastructure.persistence.postgres_delivery_log_repository import (
    PostgresDeliveryLogRepository,
)
from infrastructure.persistence.postgres_pending_push_dispatch_repository import (
    PostgresPendingPushDispatchRepository,
)
from infrastructure.persistence.postgres_preferences_repository import (
    PostgresPreferencesRepository,
)
from infrastructure.persistence.postgres_suppression_repository import (
    PostgresSuppressionRepository,
)

logger = structlog.get_logger()

DEFAULT_SCAN_INTERVAL_SECONDS = 60.0


class PendingPushDispatchScanWorker:
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
        # Every repository built from the SAME session (one transaction per
        # scan tick), mirroring ReminderScanWorker.scan_once's identical
        # convention. `now` is an explicit passthrough so tests can pin the
        # scan instant instead of racing the real wall clock.
        async with self._session_factory() as session:
            pending_push_dispatch = PostgresPendingPushDispatchRepository(session)
            preferences = PostgresPreferencesRepository(session)
            suppression = PostgresSuppressionRepository(session)
            delivery_log = PostgresDeliveryLogRepository(session)
            handler = ScanAndSendPendingPushDispatchesHandler(
                pending_push_dispatch,
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
                logger.exception("pending_push_dispatch_scan_iteration_failed")
            await asyncio.sleep(self._scan_interval_seconds)
