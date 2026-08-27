"""Domain event envelope shared by every event this service publishes.

Matches the schema documented in docs/events-catalog.md's "Format per
entry" section: event_id, aggregate_id, event_type, version, occurred_at,
payload, metadata (correlation_id, causation_id, user_id). Deliberately a
service-local copy, not shared code, per CLAUDE.md section 2.5 ("no shared
schemas across service boundaries") -- identity-service owns an identical
but independent copy.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

_PASCAL_CASE_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


@dataclass(frozen=True, slots=True)
class EventMetadata:
    correlation_id: str
    user_id: str | None = None
    causation_id: str | None = None


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_type: str
    version: int
    aggregate_id: str
    payload: dict[str, Any]
    metadata: EventMetadata
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def handler_method_suffix(self) -> str:
        """snake_case rendering of event_type (e.g. "BodyMetricRecorded" ->
        "body_metric_recorded") -- Profile.apply()'s dispatch uses this to
        build `_apply_<suffix>` method names that satisfy Python's
        snake_case naming convention (python:S100) while event_type
        itself stays PascalCase past-tense, per CLAUDE.md section 2.3's
        event-naming convention."""
        return _PASCAL_CASE_BOUNDARY.sub("_", self.event_type).lower()

    def with_payload(self, payload: dict[str, Any]) -> DomainEvent:
        # Returns a copy of this event with a different payload -- used to
        # produce the encrypted-at-rest wire copy of a plaintext domain
        # event built by the aggregate, never used to mutate an event
        # already appended to the store.
        return DomainEvent(
            event_type=self.event_type,
            version=self.version,
            aggregate_id=self.aggregate_id,
            payload=payload,
            metadata=self.metadata,
            event_id=self.event_id,
            occurred_at=self.occurred_at,
        )

    def to_wire(self) -> dict[str, Any]:
        metadata_dict = {
            "correlation_id": self.metadata.correlation_id,
            "causation_id": self.metadata.causation_id,
            "user_id": self.metadata.user_id,
        }
        return {
            "event_id": str(self.event_id),
            "aggregate_id": self.aggregate_id,
            "event_type": self.event_type,
            "version": self.version,
            "occurred_at": self.occurred_at.isoformat(),
            "payload": self.payload,
            "metadata": metadata_dict,
        }
