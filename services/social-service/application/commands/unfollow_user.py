"""UnfollowUserHandler -- backs `DELETE /api/v1/social/follows/{followee_id}`.
Pro-gated (implementation plan section 9.1's decision -- one gating rule
for the whole "acting" surface, applied uniformly). A genuine HARD delete
of the `Follow` row -- unlike `recipe-service`'s soft-unpublish-only rule,
a follow relationship has no history value once ended (implementation
plan section 1, confirmed deviation). Idempotent: not-currently-following
is a no-op, no event published."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from application.entitlement_check import is_user_entitled
from application.errors import NotEntitledError
from domain.events.user_unfollowed import build_user_unfollowed_event
from domain.ports.entitlement_cache_repository_port import EntitlementCacheRepositoryPort
from domain.ports.entitlement_check_port import EntitlementCheckPort
from domain.ports.follow_repository_port import FollowRepositoryPort
from domain.ports.outbox_repository_port import OutboxRepositoryPort


@dataclass(frozen=True, slots=True)
class UnfollowUserCommand:
    follower_id: uuid.UUID
    followee_id: uuid.UUID
    correlation_id: str


class UnfollowUserHandler:
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

    async def handle(self, command: UnfollowUserCommand) -> None:
        entitled = await is_user_entitled(
            command.follower_id, self._entitlement_cache, self._entitlement_check
        )
        if not entitled:
            raise NotEntitledError("User is not entitled to unfollow other users.")

        existing = await self._follows.get(command.follower_id, command.followee_id)
        if existing is None:
            return

        await self._follows.delete(existing.follow_id)
        await self._outbox.enqueue(
            build_user_unfollowed_event(
                follow_id=existing.follow_id,
                follower_id=existing.follower_id,
                followee_id=existing.followee_id,
                unfollowed_at=self._now_fn(),
                correlation_id=command.correlation_id,
            )
        )
