"""ProfileCreated (v1) -- see docs/events-catalog.md.

Emitted (reactively) when this service consumes UserRegistered (v1) from
identity-service and creates an empty profile aggregate for that user_id.
No synchronous call back to identity-service.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "ProfileCreated"
EVENT_VERSION = 1


def build_profile_created_event(
    user_id: uuid.UUID, correlation_id: str, causation_id: str | None = None
) -> DomainEvent:
    payload = {"user_id": str(user_id), "created_at": datetime.now(timezone.utc).isoformat()}
    metadata = EventMetadata(
        correlation_id=correlation_id, user_id=str(user_id), causation_id=causation_id
    )
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(user_id),
        payload=payload,
        metadata=metadata,
    )
