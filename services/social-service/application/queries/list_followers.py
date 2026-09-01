"""ListFollowersHandler -- backs `GET /api/v1/social/follows/followers`.
NOT Pro-gated, same rationale as `ListFollowingHandler`."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.entities.follow import Follow
from domain.ports.follow_repository_port import FollowRepositoryPort


@dataclass(frozen=True, slots=True)
class ListFollowersQuery:
    user_id: uuid.UUID


class ListFollowersHandler:
    def __init__(self, follows: FollowRepositoryPort) -> None:
        self._follows = follows

    async def handle(self, query: ListFollowersQuery) -> list[Follow]:
        return await self._follows.list_followers(query.user_id)
