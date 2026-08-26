"""EndFastingWindowCommand + handler."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from domain.entities.fasting_window import FastingWindow
from domain.ports.event_store_port import EventStorePort
from domain.ports.outbox_repository_port import OutboxRepositoryPort

AGGREGATE_TYPE = "fasting_window"


@dataclass(frozen=True, slots=True)
class EndFastingWindowCommand:
    user_id: uuid.UUID
    window_id: uuid.UUID
    correlation_id: str


@dataclass(frozen=True, slots=True)
class EndFastingWindowResult:
    window_id: uuid.UUID
    ended_at: datetime


class EndFastingWindowHandler:
    def __init__(
        self,
        event_store: EventStorePort,
        outbox: OutboxRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._event_store = event_store
        self._outbox = outbox
        self._now_fn = now_fn

    async def handle(self, command: EndFastingWindowCommand) -> EndFastingWindowResult:
        events = await self._event_store.load(AGGREGATE_TYPE, str(command.user_id))
        aggregate = FastingWindow.rebuild(command.user_id, events)

        ended_at = self._now_fn()
        event = aggregate.end_window(
            window_id=command.window_id, ended_at=ended_at, correlation_id=command.correlation_id
        )
        await self._event_store.append(AGGREGATE_TYPE, event, expected_version=len(events))
        await self._outbox.enqueue(event)
        return EndFastingWindowResult(window_id=command.window_id, ended_at=ended_at)
