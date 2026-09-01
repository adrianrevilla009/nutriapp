"""FollowUserHandler -- backs `POST /api/v1/social/follows`. Pro-gated
(implementation plan section 1.4): self-follow is rejected first (cheapest
possible check -- a pure in-memory comparison, cheaper even than the
entitlement cache lookup), then entitlement is checked BEFORE any
repository write -- an unentitled user's request never creates a `Follow`
row nor publishes an event (test-plan section 1's explicit assertions).
Idempotent: an already-existing follow returns the existing row without a
duplicate write or a duplicate `UserFollowed`."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from application.entitlement_check import is_user_entitled
from application.errors import NotEntitledError
from domain.entities.follow import Follow, SelfFollowError
from domain.events.user_followed import build_user_followed_event
from domain.ports.entitlement_cache_repository_port import EntitlementCacheRepositoryPort
from domain.ports.entitlement_check_port import EntitlementCheckPort
from domain.ports.follow_repository_port import FollowRepositoryPort
from domain.ports.outbox_repository_port import OutboxRepositoryPort

__all__ = ["FollowUserCommand", "FollowUserHandler", "SelfFollowError"]


@dataclass(frozen=True, slots=True)
class FollowUserCommand:
    follower_id: uuid.UUID
    followee_id: uuid.UUID
    correlation_id: str


class FollowUserHandler:
    def __init__(
        self,
        follows: FollowRepositoryPort,
        entitlement_cache: EntitlementCacheRepositoryPort,
        entitlement_check: EntitlementCheckPort,
        outbox: OutboxRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._follows = follows
        self._entitlement_cache = entitlement_cache
        self._entitlement_check = entitlement_check
        self._outbox = outbox
        self._now_fn = now_fn

    async def handle(self, command: FollowUserCommand) -> Follow:
        if command.follower_id == command.followee_id:
            raise SelfFollowError("A user cannot follow themselves.")

        entitled = await is_user_entitled(
            command.follower_id, self._entitlement_cache, self._entitlement_check
        )
        if not entitled:
            raise NotEntitledError("User is not entitled to follow other users.")

        existing = await self._follows.get(command.follower_id, command.followee_id)
        if existing is not None:
            return existing

        follow = Follow.create(
            follower_id=command.follower_id, followee_id=command.followee_id, now=self._now_fn()
        )
        await self._follows.save(follow)
        await self._outbox.enqueue(
            build_user_followed_event(
                follow_id=follow.follow_id,
                follower_id=follow.follower_id,
                followee_id=follow.followee_id,
                followed_at=follow.followed_at,
                correlation_id=command.correlation_id,
            )
        )
        return follow
