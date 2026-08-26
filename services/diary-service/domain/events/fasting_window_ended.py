"""FastingWindowEnded (v1) -- see docs/events-catalog.md."""

from __future__ import annotations

import uuid
from datetime import datetime

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "FastingWindowEnded"
EVENT_VERSION = 1


def build_fasting_window_ended_event(
    window_id: uuid.UUID, user_id: uuid.UUID, ended_at: datetime, correlation_id: str
) -> DomainEvent:
    payload = {
        "window_id": str(window_id),
        "user_id": str(user_id),
        "ended_at": ended_at.isoformat(),
    }
    metadata = EventMetadata(correlation_id=correlation_id, user_id=str(user_id))
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(user_id),
        payload=payload,
        metadata=metadata,
    )
