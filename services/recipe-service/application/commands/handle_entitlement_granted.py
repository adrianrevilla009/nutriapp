"""HandleEntitlementGrantedHandler -- consumes billing-service's
`EntitlementGranted` (v1), implementing this service's side of the
`ProUpgradeEntitlementPropagation` saga's fan-out (docs/sagas-and-
distributed-transactions.md). Idempotent by `event_id`: the idempotency
check short-circuits BEFORE any cache write (test-plan section 1's
explicit "cache-repository's write method called exactly once total
across both invocations" assertion)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.ports.entitlement_cache_repository_port import EntitlementCacheRepositoryPort
from domain.ports.processed_entitlement_events_repository_port import (
    ProcessedEntitlementEventsRepositoryPort,
)


@dataclass(frozen=True, slots=True)
class HandleEntitlementGrantedCommand:
    event_id: uuid.UUID
    user_id: uuid.UUID
    granted_at: datetime


class HandleEntitlementGrantedHandler:
    def __init__(
        self,
        processed_events: ProcessedEntitlementEventsRepositoryPort,
        entitlement_cache: EntitlementCacheRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._entitlement_cache = entitlement_cache

    async def handle(self, command: HandleEntitlementGrantedCommand) -> None:
        if await self._processed_events.is_processed(command.event_id):
            return
        await self._entitlement_cache.upsert(command.user_id, True, command.granted_at)
        await self._processed_events.mark_processed(command.event_id)
