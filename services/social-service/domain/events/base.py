"""The envelope every `UserFollowed`/`UserUnfollowed` outbox row is built
from and folded back into, on this service's own copy of the repo-wide
event schema (CLAUDE.md section 2.3): `event_id`, `aggregate_id`,
`event_type`, `version`, `occurred_at`, `payload`, `metadata`
(`correlation_id`, `causation_id`, `user_id`) -- see
docs/events-catalog.md's "Format per entry" section for the canonical
field list this shape has to keep matching.

Deliberately NOT imported from a shared package: ADR-0001/section 2.5
keep each service's domain layer free of any cross-service dependency,
so this envelope is reimplemented per service rather than factored out.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class EventMetadata:
    """Correlation/causation/user-id triple threaded through every publish
    (CLAUDE.md section 2.8's correlation-id propagation requirement). Every
    caller in this codebase passes these by keyword (see
    `domain/events/user_followed.py`/`user_unfollowed.py`), so field order
    here carries no positional-construction risk."""

    correlation_id: str
    causation_id: str | None = None
    user_id: str | None = None


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """In-memory form of a single outbox row -- `PostgresOutboxRepository`
    is the only adapter that constructs one from persisted state; every
    handler that enqueues a follow/unfollow event builds one fresh. Every
    construction site uses keyword arguments, same field-order note as
    `EventMetadata` above."""

    aggregate_id: str
    event_type: str
    version: int
    payload: dict[str, Any]
    metadata: EventMetadata
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_wire(self) -> dict[str, Any]:
        """Serializes for the RabbitMQ message body published by
        `RabbitMqEventPublisher` -- field names match docs/events-catalog.md
        exactly, so notification-service/analytics-service can deserialize
        without a shared schema package."""
        return {
            "event_id": str(self.event_id),
            "aggregate_id": self.aggregate_id,
            "event_type": self.event_type,
            "version": self.version,
            "occurred_at": self.occurred_at.isoformat(),
            "payload": self.payload,
            "metadata": asdict(self.metadata),
        }
