"""ProcessedEntitlementEventsRepositoryPort -- idempotency dedup for
`billing_events_consumer.py`'s `EntitlementGranted`/`EntitlementRevoked`
handling, keyed by `event_id` alone (this service has exactly one
consumer of these two event types, unlike nutrition-calculation-service's
multi-consumer `(consumer_name, event_id)` shape -- no need for that extra
key dimension here, per implementation plan section 3's single-purpose
`processed_entitlement_events` table)."""

from __future__ import annotations

import uuid
from typing import Protocol


class ProcessedEntitlementEventsRepositoryPort(Protocol):
    async def is_processed(self, event_id: uuid.UUID) -> bool: ...

    async def mark_processed(self, event_id: uuid.UUID) -> None: ...
