"""HandleEntitlementRevokedHandler -- consumes billing-service's
`EntitlementRevoked` (v1). Same idempotency-by-`event_id` shape as
`HandleEntitlementGrantedHandler`.

**Non-destructive, structurally guarded** (implementation plan section
1.2): this handler only flips the cached entitlement flag -- it has NO
reference to `FollowRepositoryPort` at all (not in its constructor, not
imported), so it is structurally impossible for revocation to delete or
hide any existing `follows`/`feed_entries` row. A downgraded user simply
cannot perform NEW follow/unfollow/feed-view actions until they
re-upgrade; their existing follow relationships persist untouched."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.ports.entitlement_cache_repository_port import EntitlementCacheRepositoryPort
from domain.ports.processed_entitlement_events_repository_port import (
    ProcessedEntitlementEventsRepositoryPort,
)


@dataclass(frozen=True, slots=True)
class HandleEntitlementRevokedCommand:
    event_id: uuid.UUID
    user_id: uuid.UUID
    revoked_at: datetime


_REVOKED_ENTITLED_VALUE = False


class HandleEntitlementRevokedHandler:
    def __init__(
        self,
        processed_events: ProcessedEntitlementEventsRepositoryPort,
        entitlement_cache: EntitlementCacheRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._entitlement_cache = entitlement_cache

    async def handle(self, command: HandleEntitlementRevokedCommand) -> None:
        already_applied = await self._processed_events.is_processed(command.event_id)
        if already_applied:
            return

        await self._entitlement_cache.upsert(
            command.user_id, _REVOKED_ENTITLED_VALUE, command.revoked_at
        )
        await self._processed_events.mark_processed(command.event_id)
