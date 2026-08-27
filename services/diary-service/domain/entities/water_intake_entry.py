"""WaterIntakeEntry aggregate root -- full event sourcing (ADR-0002). One
instance per logged item (aggregate_id = intake_id), implementation plan
section 2. A removal is a new WaterIntakeRemoved event, never a row
delete.

Zero framework imports (ADR-0001).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.events.base import DomainEvent
from domain.events.water_intake_logged import build_water_intake_logged_event
from domain.events.water_intake_removed import build_water_intake_removed_event
from domain.value_objects.water_amount_ml import WaterAmountMl


class WaterIntakeEntryNotFoundError(Exception):
    """Raised when rebuild() is given an empty event stream."""


class EntryAlreadyRemovedError(Exception):
    """Raised when remove() is called on an already-removed water intake entry."""


@dataclass(slots=True)
class WaterIntakeEntry:
    intake_id: uuid.UUID
    user_id: uuid.UUID | None = None
    amount_ml: float | None = None
    occurred_at: datetime | None = None
    removed: bool = False

    @classmethod
    def rebuild(cls, events: list[DomainEvent]) -> WaterIntakeEntry:
        if not events:
            raise WaterIntakeEntryNotFoundError(
                "Cannot rebuild a water intake entry from an empty event stream."
            )
        state = cls(intake_id=uuid.UUID(events[0].payload["intake_id"]))
        for event in events:
            state.apply(event)
        return state

    def apply(self, event: DomainEvent) -> None:
        handler = getattr(self, f"_apply_{event.handler_method_suffix}", None)
        if handler is not None:
            handler(event)

    def _apply_water_intake_logged(self, event: DomainEvent) -> None:
        self.user_id = uuid.UUID(event.payload["user_id"])
        self.amount_ml = float(event.payload["amount_ml"])
        self.occurred_at = datetime.fromisoformat(event.payload["occurred_at"])

    def _apply_water_intake_removed(self, event: DomainEvent) -> None:
        self.removed = True

    @classmethod
    def log(
        cls,
        intake_id: uuid.UUID,
        user_id: uuid.UUID,
        amount: WaterAmountMl,
        occurred_at: datetime,
        correlation_id: str,
    ) -> tuple[WaterIntakeEntry, DomainEvent]:
        entry = cls(intake_id=intake_id)
        event = build_water_intake_logged_event(
            intake_id=intake_id,
            user_id=user_id,
            amount_ml=float(amount),
            occurred_at=occurred_at,
            correlation_id=correlation_id,
        )
        entry.apply(event)
        return entry, event

    def remove(self, removed_at: datetime, correlation_id: str) -> DomainEvent:
        if self.removed:
            raise EntryAlreadyRemovedError("Water intake entry is already removed.")
        assert self.user_id is not None
        event = build_water_intake_removed_event(
            intake_id=self.intake_id,
            user_id=self.user_id,
            removed_at=removed_at,
            correlation_id=correlation_id,
        )
        self.apply(event)
        return event
