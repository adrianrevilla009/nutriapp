"""FollowRepositoryPort -- the write-model persistence boundary for the
`Follow` aggregate (event-driven CRUD, ADR-0002), plus the two read
queries `list_following`/`list_followers` need. Kept on one port (not
split into a separate read port) since this service has no CQRS split --
conventional persistence, per implementation plan section 2.

`delete` is a genuine hard delete -- unlike `recipe-service`'s
`RecipeRepositoryPort` (no delete method at all, soft-unpublish only), a
`Follow` has no history value once ended (implementation plan section 1,
confirmed deviation)."""

from __future__ import annotations

import uuid
from typing import Protocol

from domain.entities.follow import Follow


class FollowRepositoryPort(Protocol):
    async def get(self, follower_id: uuid.UUID, followee_id: uuid.UUID) -> Follow | None: ...

    async def save(self, follow: Follow) -> None: ...

    async def delete(self, follow_id: uuid.UUID) -> None: ...

    async def list_following(self, follower_id: uuid.UUID) -> list[Follow]: ...

    async def list_followers(self, followee_id: uuid.UUID) -> list[Follow]: ...
