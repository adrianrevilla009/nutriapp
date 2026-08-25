"""GoalSet (v1) -- see docs/events-catalog.md.

target_value is PLAINTEXT at the domain layer (encrypted by the
application-layer handler before persistence -- see WeightRecorded's
docstring for the shared rationale, Addendum 1 of the implementation
plan). goal_type/target_date stay in clear: needed for goal_policy
evaluation and query filtering, and neither is a biometric value alone.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "GoalSet"
EVENT_VERSION = 1


def build_goal_set_event(
    user_id: uuid.UUID,
    goal_type: str,
    target_value: float | None,
    target_date: date | None,
    set_at: datetime,
    correlation_id: str,
) -> DomainEvent:
    payload = {
        "user_id": str(user_id),
        "goal_type": goal_type,
        "target_value": target_value,
        "target_date": target_date.isoformat() if target_date is not None else None,
        "set_at": set_at.isoformat(),
    }
    metadata = EventMetadata(correlation_id=correlation_id, user_id=str(user_id))
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(user_id),
        payload=payload,
        metadata=metadata,
    )
