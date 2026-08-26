"""WaterIntakeLogged (v1) -- see docs/events-catalog.md."""

from __future__ import annotations

import uuid
from datetime import datetime

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "WaterIntakeLogged"
EVENT_VERSION = 1


def build_water_intake_logged_event(
    intake_id: uuid.UUID,
    user_id: uuid.UUID,
    amount_ml: float,
    occurred_at: datetime,
    correlation_id: str,
) -> DomainEvent:
    payload = {
        "intake_id": str(intake_id),
        "user_id": str(user_id),
        "amount_ml": amount_ml,
        "occurred_at": occurred_at.isoformat(),
    }
    metadata = EventMetadata(correlation_id=correlation_id, user_id=str(user_id))
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(intake_id),
        payload=payload,
        metadata=metadata,
    )
