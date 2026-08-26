"""RemoveWaterIntakeCommand + handler."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from application.errors import WaterIntakeAccessDeniedError, WaterIntakeEntryNotFoundError
from domain.entities.water_intake_entry import WaterIntakeEntry
from domain.ports.event_store_port import EventStorePort
from domain.ports.outbox_repository_port import OutboxRepositoryPort

AGGREGATE_TYPE = "water_intake_entry"


@dataclass(frozen=True, slots=True)
class RemoveWaterIntakeCommand:
    intake_id: uuid.UUID
    user_id: uuid.UUID
    correlation_id: str


@dataclass(frozen=True, slots=True)
class RemoveWaterIntakeResult:
    intake_id: uuid.UUID
    removed: bool


class RemoveWaterIntakeHandler:
    def __init__(
        self,
        event_store: EventStorePort,
        outbox: OutboxRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._event_store = event_store
        self._outbox = outbox
        self._now_fn = now_fn

    async def handle(self, command: RemoveWaterIntakeCommand) -> RemoveWaterIntakeResult:
        events = await self._event_store.load(AGGREGATE_TYPE, str(command.intake_id))
        if not events:
            raise WaterIntakeEntryNotFoundError(
                f"No water intake entry {command.intake_id} exists."
            )
        entry = WaterIntakeEntry.rebuild(events)
        if entry.user_id != command.user_id:
            raise WaterIntakeAccessDeniedError("This water intake entry belongs to another user.")

        event = entry.remove(removed_at=self._now_fn(), correlation_id=command.correlation_id)
        await self._event_store.append(AGGREGATE_TYPE, event, expected_version=len(events))
        await self._outbox.enqueue(event)
        return RemoveWaterIntakeResult(intake_id=command.intake_id, removed=True)
