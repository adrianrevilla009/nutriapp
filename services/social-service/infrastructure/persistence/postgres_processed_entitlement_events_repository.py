"""The idempotency ledger `BillingEventsConsumer` consults before applying
an inbound `EntitlementGranted`/`EntitlementRevoked` event a second time
-- keyed purely by `event_id`, deliberately with no aggregate/user
correlation, since an entitlement event never needs to be replayed
against a specific `follows`/`feed_entries` row."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import ProcessedEntitlementEventModel


class PostgresProcessedEntitlementEventsRepository:
    """Implements
    domain.ports.processed_entitlement_events_repository_port.ProcessedEntitlementEventsRepositoryPort.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _find(self, event_id: uuid.UUID) -> ProcessedEntitlementEventModel | None:
        return await self._session.get(ProcessedEntitlementEventModel, event_id)

    async def is_processed(self, event_id: uuid.UUID) -> bool:
        return await self._find(event_id) is not None

    async def mark_processed(self, event_id: uuid.UUID) -> None:
        if await self._find(event_id) is not None:
            return
        self._session.add(
            ProcessedEntitlementEventModel(
                event_id=event_id,
                processed_at=datetime.now(timezone.utc),
            )
        )
        await self._session.flush()
