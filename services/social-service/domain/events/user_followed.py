"""UserFollowed (v1) -- see docs/events-catalog.md. Published via Outbox
in the same DB transaction as the follows row (ADR-0002 event-driven CRUD,
implementation plan section 1.5). `aggregate_id` is the `follow_id` (the
follows row's own primary key), matching every other service's
single-id-per-row convention. Never published on an idempotent repeat
follow (`application/commands/follow_user.py`).

`followed_at` is an explicit parameter sourced from the caller's own
`now_fn`, deliberately unlike recipe-service's `build_recipe_published_event`
(which calls `datetime.now(timezone.utc)` directly inside the builder).
This keeps a single source of truth for the timestamp between the
persisted `Follow` row and the published event (no skew between the two),
and makes the event payload deterministically testable via a fake clock --
production behavior is identical either way (`now_fn` defaults to
`datetime.now(timezone.utc)`)."""

from __future__ import annotations

import uuid
from datetime import datetime

from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "UserFollowed"
EVENT_VERSION = 1


def build_user_followed_event(
    *,
    follow_id: uuid.UUID,
    follower_id: uuid.UUID,
    followee_id: uuid.UUID,
    followed_at: datetime,
    correlation_id: str,
) -> DomainEvent:
    payload = {
        "follow_id": str(follow_id),
        "follower_id": str(follower_id),
        "followee_id": str(followee_id),
        "followed_at": followed_at.isoformat(),
    }
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(follow_id),
        payload=payload,
        metadata=EventMetadata(correlation_id=correlation_id, user_id=str(follower_id)),
    )
