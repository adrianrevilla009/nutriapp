"""OutboxRelayWorker -- social-service's own background poller draining
`PostgresOutboxRepository` into RabbitMQ, following the repo-wide Outbox
Pattern relay convention (messaging-conventions SKILL.md). Publishes and
marks-published one event at a time, each in its own transaction, so a
crash mid-relay can only ever leave a row unpublished (safe to retry on
the next poll) -- never lose a row and never re-publish one already
marked done."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from domain.events.base import DomainEvent
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

    async def _fetch_pending(self, limit: int) -> list[DomainEvent]:
        async with self._session_factory() as session:
            return await PostgresOutboxRepository(session).fetch_unpublished(limit=limit)

    async def _publish_and_mark(self, event: DomainEvent) -> None:
        async with self._session_factory() as session:
            await self._publisher.publish(event)
            await PostgresOutboxRepository(session).mark_published(event.event_id)
            await session.commit()
        logger.info(
            "outbox_event_relayed",
            event_type=event.event_type,
            event_id=str(event.event_id),
            correlation_id=event.metadata.correlation_id,
        )

    async def relay_once(self, limit: int = DEFAULT_RELAY_BATCH_SIZE) -> int:
        pending = await self._fetch_pending(limit)
        for event in pending:
            await self._publish_and_mark(event)
        return len(pending)

    async def run_forever(self) -> None:
        while True:
            try:
                await self.relay_once()
            except Exception:
                logger.exception("outbox_relay_iteration_failed")
            await asyncio.sleep(self._poll_interval_seconds)
