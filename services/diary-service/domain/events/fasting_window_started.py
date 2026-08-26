"""FastingWindowStarted (v1) -- see docs/events-catalog.md.

aggregate_id is the user_id: FastingWindow is a per-user aggregate holding
the collection of that user's windows (implementation plan section 2)."""

from __future__ import annotations

import uuid
from datetime import datetime

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "FastingWindowStarted"
EVENT_VERSION = 1


def build_fasting_window_started_event(
    window_id: uuid.UUID, user_id: uuid.UUID, started_at: datetime, correlation_id: str
) -> DomainEvent:
    payload = {
        "window_id": str(window_id),
        "user_id": str(user_id),
        "started_at": started_at.isoformat(),
    }
    metadata = EventMetadata(correlation_id=correlation_id, user_id=str(user_id))
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(user_id),
        payload=payload,
        metadata=metadata,
    )
