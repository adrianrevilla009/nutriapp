"""FastingWindow aggregate root -- full event sourcing (ADR-0002). One
instance PER USER (aggregate_id = user_id), holding the set of that
user's fasting windows as entities within the aggregate -- required
because the "no overlapping windows" invariant (acceptance criterion 4)
must be enforced transactionally against ALL of a user's windows
(implementation plan section 2). This is the one deliberate deviation
from the "one instance per logged item" granularity used by the other
three aggregates in this service.

Zero framework imports (ADR-0001).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from domain.events.base import DomainEvent
from domain.events.fasting_window_ended import build_fasting_window_ended_event
from domain.events.fasting_window_started import build_fasting_window_started_event
from domain.services.fasting_overlap_policy import WindowState, is_start_allowed


class OverlappingFastingWindowError(Exception):
    """Raised when starting a window while the user already has an open one."""


class WindowAlreadyEndedError(Exception):
    """Raised when end_window() targets a window that is already ended."""


class WindowNotFoundError(Exception):
    """Raised when end_window() targets a window_id absent from this aggregate."""


@dataclass(slots=True)
class Window:
    window_id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return self.ended_at is None


@dataclass(slots=True)
class FastingWindow:
    user_id: uuid.UUID
    windows: dict[uuid.UUID, Window] = field(default_factory=dict)

    @classmethod
    def rebuild(cls, user_id: uuid.UUID, events: list[DomainEvent]) -> FastingWindow:
        state = cls(user_id=user_id)
        for event in events:
            state.apply(event)
        return state

    def apply(self, event: DomainEvent) -> None:
        handler = getattr(self, f"_apply_{event.handler_method_suffix}", None)
        if handler is not None:
            handler(event)

    def _apply_fasting_window_started(self, event: DomainEvent) -> None:
        window_id = uuid.UUID(event.payload["window_id"])
        self.windows[window_id] = Window(
            window_id=window_id,
            started_at=datetime.fromisoformat(event.payload["started_at"]),
        )

    def _apply_fasting_window_ended(self, event: DomainEvent) -> None:
        window_id = uuid.UUID(event.payload["window_id"])
        window = self.windows.get(window_id)
        if window is not None:
            window.ended_at = datetime.fromisoformat(event.payload["ended_at"])

    @property
    def open_window(self) -> Window | None:
        for window in self.windows.values():
            if window.is_open:
                return window
        return None

    def start_window(
        self, window_id: uuid.UUID, started_at: datetime, correlation_id: str
    ) -> DomainEvent:
        window_states = [
            WindowState(w.window_id, w.started_at, w.ended_at) for w in self.windows.values()
        ]
        if not is_start_allowed(window_states):
            raise OverlappingFastingWindowError(
                "This user already has an open fasting window -- end it before starting a new one."
            )
        event = build_fasting_window_started_event(
            window_id=window_id,
            user_id=self.user_id,
            started_at=started_at,
            correlation_id=correlation_id,
        )
        self.apply(event)
        return event

    def end_window(
        self, window_id: uuid.UUID, ended_at: datetime, correlation_id: str
    ) -> DomainEvent:
        window = self.windows.get(window_id)
        if window is None:
            raise WindowNotFoundError(f"No fasting window {window_id} for this user.")
        if not window.is_open:
            raise WindowAlreadyEndedError(f"Fasting window {window_id} is already ended.")
        event = build_fasting_window_ended_event(
            window_id=window_id,
            user_id=self.user_id,
            ended_at=ended_at,
            correlation_id=correlation_id,
        )
        self.apply(event)
        return event
