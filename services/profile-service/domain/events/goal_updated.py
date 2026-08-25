"""GoalUpdated (v1) -- see docs/events-catalog.md.

Same payload shape as GoalSet plus `previous_goal_type` (implementation
plan section 5). target_value PLAINTEXT at the domain layer, same
encrypt-before-persist rule as GoalSet.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "GoalUpdated"
EVENT_VERSION = 1


def build_goal_updated_event(
    user_id: uuid.UUID,
    goal_type: str,
    target_value: float | None,
    target_date: date | None,
    set_at: datetime,
    previous_goal_type: str,
    correlation_id: str,
) -> DomainEvent:
    payload = {
        "user_id": str(user_id),
        "goal_type": goal_type,
        "target_value": target_value,
        "target_date": target_date.isoformat() if target_date is not None else None,
        "set_at": set_at.isoformat(),
        "previous_goal_type": previous_goal_type,
    }
    metadata = EventMetadata(correlation_id=correlation_id, user_id=str(user_id))
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(user_id),
        payload=payload,
        metadata=metadata,
    )
