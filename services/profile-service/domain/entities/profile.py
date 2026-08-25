"""Profile aggregate root -- full event sourcing (ADR-0002).

Zero framework imports (ADR-0001). Current state is never stored
directly; it is always derived by folding over the aggregate's event
stream (`rebuild`). Commands are validated against the current derived
state and, on success, produce a new DomainEvent -- appended to the event
store atomically with an outbox row by the application layer, never
mutated afterward (a correction is always a new event).

Encryption note: every DomainEvent this aggregate builds carries a
PLAINTEXT payload (no I/O allowed at this layer). The application-layer
command handler is responsible for producing the encrypted-at-rest copy
(DomainEvent.with_payload + DataEncryptionPort) before persisting/
outboxing it, and for decrypting persisted events back to plaintext
before calling `rebuild()` again on a later command. See
application/dto/event_crypto.py.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.events.base import DomainEvent
from domain.events.biometric_consent_granted import build_biometric_consent_granted_event
from domain.events.body_metric_recorded import (
    SUPPORTED_METRIC_TYPES,
    build_body_metric_recorded_event,
)
from domain.events.goal_set import build_goal_set_event
from domain.events.goal_updated import build_goal_updated_event
from domain.events.profile_created import build_profile_created_event
from domain.events.weight_recorded import build_weight_recorded_event
from domain.value_objects.goal_target import GoalTarget
from domain.value_objects.goal_type import GoalType
from domain.value_objects.weight_kg import WeightKg


class ConsentRequiredError(Exception):
    """Raised when a metric-recording command is attempted before
    BiometricConsentGranted has been recorded for this profile."""


class UnsupportedMetricTypeError(Exception):
    """Raised when record_body_metric is called with an unknown metric_type."""


class GoalAlreadyExistsError(Exception):
    """Raised when set_goal is called on a profile that already has a goal --
    use update_goal instead."""


class NoExistingGoalError(Exception):
    """Raised when update_goal is called on a profile with no goal yet."""


class ProfileNotFoundError(Exception):
    """Raised when rebuild() is given an empty event stream."""


@dataclass(slots=True)
class Profile:
    user_id: uuid.UUID
    exists: bool = False
    consent_granted: bool = False
    weight_kg: float | None = None
    body_metrics: dict[str, Any] = field(default_factory=dict)
    goal_type: GoalType | None = None
    goal_target_value: float | None = None
    goal_target_date: date | None = None

    @classmethod
    def rebuild(cls, events: list[DomainEvent]) -> Profile:
        if not events:
            raise ProfileNotFoundError("Cannot rebuild a profile from an empty event stream.")
        first = events[0]
        state = cls(user_id=uuid.UUID(first.payload["user_id"]))
        for event in events:
            state.apply(event)
        return state

    def apply(self, event: DomainEvent) -> None:
        handler = getattr(self, f"_apply_{event.event_type}", None)
        if handler is not None:
            handler(event)

    def _apply_ProfileCreated(self, event: DomainEvent) -> None:
        self.exists = True

    def _apply_BiometricConsentGranted(self, event: DomainEvent) -> None:
        self.consent_granted = True

    def _apply_WeightRecorded(self, event: DomainEvent) -> None:
        self.weight_kg = float(event.payload["weight_kg"])

    def _apply_BodyMetricRecorded(self, event: DomainEvent) -> None:
        self.body_metrics[event.payload["metric_type"]] = event.payload["value"]

    def _apply_GoalSet(self, event: DomainEvent) -> None:
        self._apply_goal_payload(event)

    def _apply_GoalUpdated(self, event: DomainEvent) -> None:
        self._apply_goal_payload(event)

    def _apply_goal_payload(self, event: DomainEvent) -> None:
        self.goal_type = GoalType.from_value(event.payload["goal_type"])
        target_value = event.payload.get("target_value")
        self.goal_target_value = float(target_value) if target_value is not None else None
        target_date = event.payload.get("target_date")
        self.goal_target_date = date.fromisoformat(target_date) if target_date else None

    @classmethod
    def create(
        cls, user_id: uuid.UUID, correlation_id: str, causation_id: str | None = None
    ) -> tuple[Profile, DomainEvent]:
        profile = cls(user_id=user_id)
        event = build_profile_created_event(
            user_id=user_id, correlation_id=correlation_id, causation_id=causation_id
        )
        profile.apply(event)
        return profile, event

    def grant_consent(self, granted_at: datetime, correlation_id: str) -> DomainEvent:
        event = build_biometric_consent_granted_event(
            user_id=self.user_id, granted_at=granted_at, correlation_id=correlation_id
        )
        self.apply(event)
        return event

    def record_weight(
        self, weight: WeightKg, recorded_at: datetime, correlation_id: str
    ) -> DomainEvent:
        if not self.consent_granted:
            raise ConsentRequiredError("Biometric consent has not been granted.")
        event = build_weight_recorded_event(
            user_id=self.user_id,
            weight_kg=float(weight),
            recorded_at=recorded_at,
            correlation_id=correlation_id,
        )
        self.apply(event)
        return event

    def record_body_metric(
        self, metric_type: str, value: Any, recorded_at: datetime, correlation_id: str
    ) -> DomainEvent:
        if not self.consent_granted:
            raise ConsentRequiredError("Biometric consent has not been granted.")
        if metric_type not in SUPPORTED_METRIC_TYPES:
            raise UnsupportedMetricTypeError(f"Unsupported metric_type: {metric_type!r}")
        event = build_body_metric_recorded_event(
            user_id=self.user_id,
            metric_type=metric_type,
            value=value,
            recorded_at=recorded_at,
            correlation_id=correlation_id,
        )
        self.apply(event)
        return event

    def set_goal(
        self, goal_type: GoalType, goal_target: GoalTarget, set_at: datetime, correlation_id: str
    ) -> DomainEvent:
        if self.goal_type is not None:
            raise GoalAlreadyExistsError("A goal already exists -- use update_goal() instead.")
        event = build_goal_set_event(
            user_id=self.user_id,
            goal_type=goal_type.value,
            target_value=goal_target.target_value,
            target_date=goal_target.target_date,
            set_at=set_at,
            correlation_id=correlation_id,
        )
        self.apply(event)
        return event

    def update_goal(
        self, goal_type: GoalType, goal_target: GoalTarget, set_at: datetime, correlation_id: str
    ) -> DomainEvent:
        if self.goal_type is None:
            raise NoExistingGoalError("No existing goal to update -- use set_goal() instead.")
        previous_goal_type = self.goal_type.value
        event = build_goal_updated_event(
            user_id=self.user_id,
            goal_type=goal_type.value,
            target_value=goal_target.target_value,
            target_date=goal_target.target_date,
            set_at=set_at,
            previous_goal_type=previous_goal_type,
            correlation_id=correlation_id,
        )
        self.apply(event)
        return event
