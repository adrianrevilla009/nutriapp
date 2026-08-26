"""LogWaterIntakeCommand + handler."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from domain.entities.water_intake_entry import WaterIntakeEntry
from domain.ports.event_store_port import EventStorePort
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.value_objects.water_amount_ml import WaterAmountMl

AGGREGATE_TYPE = "water_intake_entry"


@dataclass(frozen=True, slots=True)
class LogWaterIntakeCommand:
    user_id: uuid.UUID
    amount_ml: float
    occurred_at: datetime
    correlation_id: str


@dataclass(frozen=True, slots=True)
class LogWaterIntakeResult:
    intake_id: uuid.UUID
    amount_ml: float
    occurred_at: datetime


class LogWaterIntakeHandler:
    def __init__(
        self,
        event_store: EventStorePort,
        outbox: OutboxRepositoryPort,
        id_fn: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._event_store = event_store
        self._outbox = outbox
        self._id_fn = id_fn

    async def handle(self, command: LogWaterIntakeCommand) -> LogWaterIntakeResult:
        intake_id = self._id_fn()
        _entry, event = WaterIntakeEntry.log(
            intake_id=intake_id,
            user_id=command.user_id,
            amount=WaterAmountMl(command.amount_ml),
            occurred_at=command.occurred_at,
            correlation_id=command.correlation_id,
        )
        await self._event_store.append(AGGREGATE_TYPE, event, expected_version=0)
        await self._outbox.enqueue(event)
        return LogWaterIntakeResult(
            intake_id=intake_id, amount_ml=command.amount_ml, occurred_at=command.occurred_at
        )
