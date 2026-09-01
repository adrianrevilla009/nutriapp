"""social-service's side of the `ProUpgradeEntitlementPropagation` saga's
fan-out (docs/sagas-and-distributed-transactions.md): consumes
billing-service's `EntitlementGranted` (v1) and flips this service's own
`entitlement_cache` row to entitled=True. social-service is the SECOND
real consumer of this event (recipe-service was the first).

Idempotency contract: `ProcessedEntitlementEventsRepositoryPort.is_processed`
is checked, and short-circuits, BEFORE the cache is ever touched -- a
redelivered event must produce exactly one cache write total, never two
(test-plan section 1's explicit assertion)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.ports.entitlement_cache_repository_port import EntitlementCacheRepositoryPort
from domain.ports.processed_entitlement_events_repository_port import (
    ProcessedEntitlementEventsRepositoryPort,
)

_GRANTED_ENTITLED_VALUE = True


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
        already_applied = await self._processed_events.is_processed(command.event_id)
        if already_applied:
            return

        await self._entitlement_cache.upsert(
            command.user_id, _GRANTED_ENTITLED_VALUE, command.granted_at
        )
        await self._processed_events.mark_processed(command.event_id)
