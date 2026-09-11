"""ProcessedEntitlementEventsRepositoryPort -- idempotency ledger for
billing-service's EntitlementGranted/EntitlementRevoked, dedicated to the
new `billing_events_consumer.py` (implementation plan addendum,
2026-09-08: `entitlement_cache` live writer approved). One independent
ledger per independent consumer, same convention as this service's other
three `processed_*_events` ports (`already_processed`/`mark_processed`,
not `is_processed` -- deliberately kept consistent with this service's
own established naming rather than matching analytics-service's port of
the same underlying idea literally)."""

from __future__ import annotations

import uuid
from typing import Protocol


class ProcessedEntitlementEventsRepositoryPort(Protocol):
    async def already_processed(self, event_id: uuid.UUID) -> bool: ...

    async def mark_processed(self, event_id: uuid.UUID) -> None: ...
