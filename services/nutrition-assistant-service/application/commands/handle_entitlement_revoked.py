"""HandleEntitlementRevokedHandler -- only flips the cached flag, never
touches `diary_history`/`nutrition_history`/`analytics_signals`
(non-destructive, structural guard: this handler's constructor has no
reference to any of those repositories at all, mirroring
recipe-service's/social-service's/analytics-service's identical handler)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.ports.entitlement_cache_repository_port import EntitlementCacheRepositoryPort
from domain.ports.processed_entitlement_events_repository_port import (
    ProcessedEntitlementEventsRepositoryPort,
)

_REVOKED_ENTITLED_VALUE = False


@dataclass(frozen=True, slots=True)
class HandleEntitlementRevokedCommand:
    event_id: uuid.UUID
    user_id: uuid.UUID
    revoked_at: datetime


class HandleEntitlementRevokedHandler:
    def __init__(
        self,
        processed_events: ProcessedEntitlementEventsRepositoryPort,
        entitlement_cache: EntitlementCacheRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._entitlement_cache = entitlement_cache

    async def handle(self, command: HandleEntitlementRevokedCommand) -> None:
        if await self._processed_events.already_processed(command.event_id):
            return

        await self._entitlement_cache.upsert(
            command.user_id, _REVOKED_ENTITLED_VALUE, command.revoked_at
        )
        await self._processed_events.mark_processed(command.event_id)
