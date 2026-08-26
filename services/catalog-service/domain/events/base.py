"""Domain event envelope shared by every event this service publishes.

Matches the schema documented in docs/events-catalog.md's "Format per
entry" section: event_id, aggregate_id, event_type, version, occurred_at,
payload, metadata (correlation_id, causation_id, user_id).

Mirrors services/identity-service/domain/events/base.py exactly — the
envelope shape is a repo-wide convention, not something this service
should reinvent.
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
        return {
            "event_id": str(self.event_id),
            "aggregate_id": self.aggregate_id,
            "event_type": self.event_type,
            "version": self.version,
            "occurred_at": self.occurred_at.isoformat(),
            "payload": self.payload,
            "metadata": {
                "correlation_id": self.metadata.correlation_id,
                "causation_id": self.metadata.causation_id,
                "user_id": self.metadata.user_id,
            },
        }
