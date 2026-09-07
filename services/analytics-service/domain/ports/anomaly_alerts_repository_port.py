"""AnomalyAlertsRepositoryPort -- append-only log of detected/published
`NutrientDeficiencyDetected` signals, doubling as the 14-day cooldown
dedup guard (implementation plan section 9 addendum, resolution 2):
`most_recent_detection_at` returns `None` if this exact user/signal pair
has never been recorded, letting the handler compute
`now - most_recent_detection_at < cooldown` itself (pure, testable) rather
than pushing the cooldown-window math into the adapter."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol


class AnomalyAlertsRepositoryPort(Protocol):
    async def most_recent_detection_at(
        self, user_id: uuid.UUID, signal: str
    ) -> datetime | None: ...

    async def record_detection(
        self, user_id: uuid.UUID, signal: str, window_days: int, value: float, detected_at: datetime
    ) -> None: ...
