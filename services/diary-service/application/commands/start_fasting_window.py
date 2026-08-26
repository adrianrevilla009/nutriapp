"""StartFastingWindowCommand + handler. FastingWindow is a per-user
aggregate (aggregate_id = user_id) -- see implementation plan section 2."""

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
class StartFastingWindowCommand:
    user_id: uuid.UUID
    correlation_id: str


@dataclass(frozen=True, slots=True)
class StartFastingWindowResult:
    window_id: uuid.UUID
    started_at: datetime


class StartFastingWindowHandler:
    def __init__(
        self,
        event_store: EventStorePort,
        outbox: OutboxRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        id_fn: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._event_store = event_store
        self._outbox = outbox
        self._now_fn = now_fn
        self._id_fn = id_fn

    async def handle(self, command: StartFastingWindowCommand) -> StartFastingWindowResult:
        events = await self._event_store.load(AGGREGATE_TYPE, str(command.user_id))
        aggregate = FastingWindow.rebuild(command.user_id, events)

        window_id = self._id_fn()
        started_at = self._now_fn()
        event = aggregate.start_window(
            window_id=window_id, started_at=started_at, correlation_id=command.correlation_id
        )
        await self._event_store.append(AGGREGATE_TYPE, event, expected_version=len(events))
        await self._outbox.enqueue(event)
        return StartFastingWindowResult(window_id=window_id, started_at=started_at)
