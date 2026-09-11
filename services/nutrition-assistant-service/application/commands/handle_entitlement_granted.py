"""HandleEntitlementGrantedHandler -- this service's side of the
`ProUpgradeEntitlementPropagation` saga's fan-out (implementation plan
addendum, 2026-09-08: `entitlement_cache` live writer approved).
nutrition-assistant-service is the FOURTH real consumer of this event
(after recipe-service, social-service, analytics-service).

Idempotency contract: `already_processed` is checked, and short-circuits,
BEFORE the cache is ever touched -- a redelivered event must produce
exactly one cache write total."""

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
        if await self._processed_events.already_processed(command.event_id):
            return

        await self._entitlement_cache.upsert(
            command.user_id, _GRANTED_ENTITLED_VALUE, command.granted_at
        )
        await self._processed_events.mark_processed(command.event_id)
