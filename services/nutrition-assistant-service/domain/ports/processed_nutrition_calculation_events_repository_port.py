"""ProcessedNutritionCalculationEventsRepositoryPort -- idempotency ledger
for nutrition-calculation-service's two consumed event types."""

from __future__ import annotations

import uuid
from typing import Protocol


class ProcessedNutritionCalculationEventsRepositoryPort(Protocol):
    async def already_processed(self, event_id: uuid.UUID) -> bool: ...

    async def mark_processed(self, event_id: uuid.UUID) -> None: ...
