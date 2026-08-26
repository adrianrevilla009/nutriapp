"""WaterIntakeRemoved (v1) -- see docs/events-catalog.md."""

from __future__ import annotations

import uuid
from datetime import datetime

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "WaterIntakeRemoved"
EVENT_VERSION = 1


def build_water_intake_removed_event(
    intake_id: uuid.UUID, user_id: uuid.UUID, removed_at: datetime, correlation_id: str
) -> DomainEvent:
    payload = {
        "intake_id": str(intake_id),
        "user_id": str(user_id),
        "removed_at": removed_at.isoformat(),
    }
    metadata = EventMetadata(correlation_id=correlation_id, user_id=str(user_id))
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(intake_id),
        payload=payload,
        metadata=metadata,
    )
