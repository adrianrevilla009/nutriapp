"""ProcessedEventsPort -- idempotency dedup shared across all 3 inbound
consumers (implementation plan section 3), keyed by `(consumer_name,
event_id)` rather than `event_id` alone, since a single `event_id` could
in principle need independent dedup state per consumer if this service
ever gains overlapping consumers of the same exchange.
"""

from __future__ import annotations

import uuid
from typing import Protocol


class ProcessedEventsPort(Protocol):
    async def already_processed(self, consumer_name: str, event_id: uuid.UUID) -> bool: ...

    async def mark_processed(self, consumer_name: str, event_id: uuid.UUID) -> None: ...
