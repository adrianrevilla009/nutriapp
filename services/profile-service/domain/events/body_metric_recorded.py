"""BodyMetricRecorded (v1) -- see docs/events-catalog.md.

metric_type is one of "height", "age", "sex", "activity_level". Payload's
`value` is PLAINTEXT at the domain layer, same encrypt-before-persist rule
as WeightRecorded (see that module's docstring).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "BodyMetricRecorded"
EVENT_VERSION = 1

SUPPORTED_METRIC_TYPES = ("height", "age", "sex", "activity_level")


def build_body_metric_recorded_event(
    user_id: uuid.UUID,
    metric_type: str,
    value: Any,
    recorded_at: datetime,
    correlation_id: str,
) -> DomainEvent:
    payload = {
        "user_id": str(user_id),
        "metric_type": metric_type,
        "value": value,
        "recorded_at": recorded_at.isoformat(),
    }
    metadata = EventMetadata(correlation_id=correlation_id, user_id=str(user_id))
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(user_id),
        payload=payload,
        metadata=metadata,
    )
