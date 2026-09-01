"""UserUnfollowed (v1) -- see docs/events-catalog.md. Published via Outbox
in the same DB transaction as the follows row's deletion (ADR-0002
event-driven CRUD, implementation plan section 1.5). `aggregate_id` is the
`follow_id` -- the (now-deleted) follows row's own former primary key,
matching every other service's single-id-per-row convention. Never
published for a follow relationship that did not exist (idempotent no-op,
`application/commands/unfollow_user.py`).

`unfollowed_at` is an explicit parameter sourced from the caller's own
`now_fn`, for the same reason documented in `user_followed.py`: a single
source of truth for the timestamp and deterministic test injection,
deliberately unlike recipe-service's wall-clock-in-builder pattern."""

from __future__ import annotations

import uuid
from datetime import datetime

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "UserUnfollowed"
EVENT_VERSION = 1


def build_user_unfollowed_event(
    *,
    follow_id: uuid.UUID,
    follower_id: uuid.UUID,
    followee_id: uuid.UUID,
    unfollowed_at: datetime,
    correlation_id: str,
) -> DomainEvent:
    payload = {
        "follow_id": str(follow_id),
        "follower_id": str(follower_id),
        "followee_id": str(followee_id),
        "unfollowed_at": unfollowed_at.isoformat(),
    }
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(follow_id),
        payload=payload,
        metadata=EventMetadata(correlation_id=correlation_id, user_id=str(follower_id)),
    )
