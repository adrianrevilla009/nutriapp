"""Follow -- the write-model aggregate for this service's one-way
connection between two users (event-driven CRUD, ADR-0002: conventional
persistence, not event-sourced). One row per (follower_id, followee_id)
pair, enforced at the DB layer by a unique constraint (defense-in-depth
beneath this application's own idempotency check,
`application/commands/follow_user.py`).

Self-follow is rejected STRUCTURALLY here, in `__post_init__` -- not just
an application-layer check -- so a `Follow` with `follower_id ==
followee_id` can never exist as a valid instance anywhere in this codebase
(implementation plan section 1, test-plan section 1's explicit "structural
guard" requirement).

Unlike `recipe-service`'s `Recipe` (soft-unpublish only, never a hard
delete), a `Follow` has no "history" value once the relationship ends --
`UnfollowUserHandler` performs a genuine hard delete of the row. This is a
deliberate, confirmed deviation from `recipe-service`'s soft-delete
convention (implementation plan section 1, "explicit deviation... not
copy-pasting blindly")."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


class SelfFollowError(ValueError):
    """Raised when `follower_id == followee_id` -- a user cannot follow
    themselves. Structural guard: raised from `__post_init__`, so it fires
    for any construction path, not only `Follow.create`."""


@dataclass(frozen=True, slots=True)
class Follow:
    follow_id: uuid.UUID
    follower_id: uuid.UUID
    followee_id: uuid.UUID
    followed_at: datetime

    def __post_init__(self) -> None:
        if self.follower_id == self.followee_id:
            raise SelfFollowError("A user cannot follow themselves.")

    @classmethod
    def create(cls, *, follower_id: uuid.UUID, followee_id: uuid.UUID, now: datetime) -> Follow:
        return cls(
            follow_id=uuid.uuid4(),
            follower_id=follower_id,
            followee_id=followee_id,
            followed_at=now,
        )
