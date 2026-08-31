"""Domain event envelope shared by every event this service publishes.

Matches the schema documented in docs/events-catalog.md's "Format per
entry" section: event_id, aggregate_id, event_type, version, occurred_at,
payload, metadata (correlation_id, causation_id, user_id).

Mirrors services/billing-service/domain/events/base.py exactly -- the
envelope shape is a repo-wide convention, not something this service
should reinvent (each service keeps its own copy per CLAUDE.md section
2.5's event schema, to avoid a cross-service domain-layer dependency).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


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

    def to_wire(self) -> dict[str, Any]:
        wire_metadata = {
            "correlation_id": self.metadata.correlation_id,
            "causation_id": self.metadata.causation_id,
            "user_id": self.metadata.user_id,
        }
        wire: dict[str, Any] = {}
        wire["event_id"] = str(self.event_id)
        wire["aggregate_id"] = self.aggregate_id
        wire["event_type"] = self.event_type
        wire["version"] = self.version
        wire["occurred_at"] = self.occurred_at.isoformat()
        wire["payload"] = self.payload
        wire["metadata"] = wire_metadata
        return wire
