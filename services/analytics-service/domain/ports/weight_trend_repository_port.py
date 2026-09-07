"""WeightTrendRepositoryPort -- stores `WeightRecorded`'s ciphertext field
as-is. This service never decrypts it (ADR-0023's non-decrypting posture,
already used by `nutrition-calculation-service` for the same field)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Protocol


class WeightTrendRepositoryPort(Protocol):
    async def upsert(
        self, user_id: uuid.UUID, on_date: date, weight_kg_ciphertext: str, recorded_at: datetime
    ) -> None: ...
