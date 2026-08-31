"""ProcessedEntitlementEventsRepositoryPort -- idempotency dedup for
`billing_events_consumer.py`'s `EntitlementGranted`/`EntitlementRevoked`
handling, keyed by `event_id` alone. This service has exactly one consumer
of these two event types, so no `(consumer_name, event_id)` composite key
is needed -- mirrors `recipe-service`'s identical port/table design.
Independent from `ProcessedRecipeEventsRepositoryPort` -- two separate
idempotency ledgers for two separate, independent consumers (implementation
plan section 3)."""

from __future__ import annotations

import uuid
from typing import Protocol


class ProcessedEntitlementEventsRepositoryPort(Protocol):
    async def is_processed(self, event_id: uuid.UUID) -> bool: ...

    async def mark_processed(self, event_id: uuid.UUID) -> None: ...
