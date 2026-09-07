"""The envelope every `NutrientDeficiencyDetected` outbox row is built
from and folded back into -- this service's own copy of the repo-wide
event schema (CLAUDE.md section 2.3): `event_id`, `aggregate_id`,
`event_type`, `version`, `occurred_at`, `payload`, `metadata`
(`correlation_id`, `causation_id`, `user_id`) -- see
docs/events-catalog.md's "Format per entry" section.

Deliberately NOT imported from a shared package: ADR-0001/CLAUDE.md
section 2.5 keep each service's domain layer free of any cross-service
dependency, so this envelope is reimplemented per service (identical
shape to social-service's/recipe-service's own copy) rather than
factored out.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class EventMetadata:
    correlation_id: str
    causation_id: str | None = None
    user_id: str | None = None


@dataclass(frozen=True, slots=True)
class DomainEvent:
    aggregate_id: str
    event_type: str
    version: int
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
            "metadata": asdict(self.metadata),
        }
