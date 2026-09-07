"""HandleWeightRecordedHandler -- projects `WeightRecorded` (profile-service)
into `weight_trend`, storing the AES-256-GCM ciphertext field as-is.
This service never decrypts it (ADR-0023's non-decrypting posture,
already used by `nutrition-calculation-service` for the identical field
-- test-plan section 2's explicit "assert no decryption call is made
anywhere" requirement is satisfied structurally: nothing in this handler
or its dependencies has a decrypt capability at all)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.ports.processed_profile_events_repository_port import (
    ProcessedProfileEventsRepositoryPort,
)
from domain.ports.weight_trend_repository_port import WeightTrendRepositoryPort


@dataclass(frozen=True, slots=True)
class HandleWeightRecordedCommand:
    event_id: uuid.UUID
    user_id: uuid.UUID
    weight_kg_ciphertext: str
    recorded_at: datetime


class HandleWeightRecordedHandler:
    def __init__(
        self,
        processed_events: ProcessedProfileEventsRepositoryPort,
        weight_trend: WeightTrendRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._weight_trend = weight_trend

    async def handle(self, command: HandleWeightRecordedCommand) -> None:
        if await self._processed_events.is_processed(command.event_id):
            return

        await self._weight_trend.upsert(
            user_id=command.user_id,
            on_date=command.recorded_at.date(),
            weight_kg_ciphertext=command.weight_kg_ciphertext,
            recorded_at=command.recorded_at,
        )
        await self._processed_events.mark_processed(command.event_id)
