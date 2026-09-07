"""ProcessedDiaryEventsRepositoryPort -- idempotency ledger for
diary-service's five consumed event types (one shared ledger, same
convention analytics-service's ProcessedDiaryEventsRepositoryPort uses,
since they are all diary-service's own events)."""

from __future__ import annotations

import uuid
from typing import Protocol


class ProcessedDiaryEventsRepositoryPort(Protocol):
    async def already_processed(self, event_id: uuid.UUID) -> bool: ...

    async def mark_processed(self, event_id: uuid.UUID) -> None: ...
