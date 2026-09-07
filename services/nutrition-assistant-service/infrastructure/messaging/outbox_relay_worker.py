"""OutboxRelayWorker -- scaffolded for architectural symmetry with every
other event-driven-CRUD service in this repo (ADR-0002 addendum). Unused
this pass: no live EventPublisherPort adapter is wired to a real exchange
(implementation plan section 5, no other service consumes anything from
this one yet). NOT started as a background task from
infrastructure/composition_root.py this pass -- present so the shape
exists and is tested (a scaffold-doesn't-silently-break smoke test, per
the persisted test plan section 3), not silently pretended to be fully
wired."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from domain.ports.event_publisher_port import EventPublisherPort
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository

logger = structlog.get_logger()

DEFAULT_POLL_INTERVAL_SECONDS = 2.0
DEFAULT_RELAY_BATCH_SIZE = 100


class OutboxRelayWorker:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        publisher: EventPublisherPort,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> None:
        self._session_factory = session_factory
        self._publisher = publisher
        self._poll_interval_seconds = poll_interval_seconds

    async def relay_once(self, limit: int = DEFAULT_RELAY_BATCH_SIZE) -> int:
        async with self._session_factory() as session:
            pending = await PostgresOutboxRepository(session).fetch_unpublished(limit=limit)

        for event in pending:
            await self._publisher.publish(event)
            async with self._session_factory() as session:
                await PostgresOutboxRepository(session).mark_published(uuid.UUID(event["event_id"]))
                await session.commit()

        return len(pending)

    async def run_forever(self) -> None:
        while True:
            try:
                await self.relay_once()
            except Exception:
                logger.exception("outbox_relay_iteration_failed")
            await asyncio.sleep(self._poll_interval_seconds)
