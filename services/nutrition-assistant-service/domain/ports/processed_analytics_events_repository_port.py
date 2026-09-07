"""ProcessedAnalyticsEventsRepositoryPort -- idempotency ledger for
analytics-service's NutrientDeficiencyDetected event."""

from __future__ import annotations

import uuid
from typing import Protocol


class ProcessedAnalyticsEventsRepositoryPort(Protocol):
    async def already_processed(self, event_id: uuid.UUID) -> bool: ...

    async def mark_processed(self, event_id: uuid.UUID) -> None: ...
