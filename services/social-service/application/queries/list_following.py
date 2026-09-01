"""ListFollowingHandler -- backs `GET /api/v1/social/follows/following`.
NOT Pro-gated -- viewing your own connection list is not the gated
feature, only acting (follow/unfollow/feed) is (implementation plan
section 1's acceptance criterion 3). Structural guard: this handler has no
reference to any entitlement port at all -- an unentitled user's request
can never be rejected because there is nothing here that could reject it
(test-plan section 1's "assert no entitlement-port call is made at all"
case)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.entities.follow import Follow
from domain.ports.follow_repository_port import FollowRepositoryPort


@dataclass(frozen=True, slots=True)
class ListFollowingQuery:
    user_id: uuid.UUID


class ListFollowingHandler:
    def __init__(self, follows: FollowRepositoryPort) -> None:
        self._follows = follows

    async def handle(self, query: ListFollowingQuery) -> list[Follow]:
        return await self._follows.list_following(query.user_id)
