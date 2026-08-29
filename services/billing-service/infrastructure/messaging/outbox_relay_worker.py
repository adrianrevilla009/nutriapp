"""OutboxRelayWorker -- mirrors services/catalog-service's adapter exactly
(messaging-conventions SKILL.md's Outbox Pattern relay is a repo-wide
convention). Each event is published and marked-published individually so
a crash mid-relay never loses an event and never republishes an
already-published row."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from domain.ports.event_publisher_port import EventPublisherPort
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository

logger = structlog.get_logger()

DEFAULT_POLL_INTERVAL_SECONDS = 2.0


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

    async def relay_once(self, limit: int = 100) -> int:
        published_count = 0
        async with self._session_factory() as session:
            outbox = PostgresOutboxRepository(session)
            pending = await outbox.fetch_unpublished(limit=limit)

        for event in pending:
            async with self._session_factory() as session:
                outbox = PostgresOutboxRepository(session)
                await self._publisher.publish(event)
                await outbox.mark_published(event.event_id)
                await session.commit()
                published_count += 1
                logger.info(
                    "outbox_event_relayed",
                    event_type=event.event_type,
                    event_id=str(event.event_id),
                    correlation_id=event.metadata.correlation_id,
                )
        return published_count

    async def run_forever(self) -> None:
        while True:
            try:
                await self.relay_once()
            except Exception:
                logger.exception("outbox_relay_iteration_failed")
            await asyncio.sleep(self._poll_interval_seconds)
