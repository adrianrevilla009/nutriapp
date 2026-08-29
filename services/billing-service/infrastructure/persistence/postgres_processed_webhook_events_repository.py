"""PostgresProcessedWebhookEventsRepository -- implements
ProcessedWebhookEventsRepositoryPort. Backs webhook idempotency (dedupe by
Stripe's own event `id`)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import ProcessedWebhookEventModel


class PostgresProcessedWebhookEventsRepository:
    """Implements
    domain.ports.processed_webhook_events_repository_port.ProcessedWebhookEventsRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_processed(self, stripe_event_id: str) -> bool:
        stmt = select(ProcessedWebhookEventModel).where(
            ProcessedWebhookEventModel.stripe_event_id == stripe_event_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def mark_processed(self, stripe_event_id: str) -> None:
        existing = await self._session.get(ProcessedWebhookEventModel, stripe_event_id)
        if existing is not None:
            return
        row = ProcessedWebhookEventModel(
            stripe_event_id=stripe_event_id, processed_at=datetime.now(timezone.utc)
        )
        self._session.add(row)
        await self._session.flush()
