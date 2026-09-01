"""FeedRepositoryPort -- the local, event-projected `feed_entries` read
table (implementation plan section 1.3, fan-out-on-read). `upsert` is
keyed by `recipe_id` (one row per recipe, at most one feed_entries row per
published recipe); `delete_by_recipe_id` removes it synchronously with
`RecipeUnpublished` consumption -- never a scheduled recompute
(`social-agent.md`'s "must take effect immediately" rule).
`list_for_authors` is the join half of `GET /feed`: given the caller's own
followed author ids, return only feed entries from THOSE authors --
`GetFeedHandler` never queries unfiltered."""

from __future__ import annotations

import uuid
from typing import Protocol

from domain.value_objects.feed_entry import FeedEntry


class FeedRepositoryPort(Protocol):
    async def upsert(self, entry: FeedEntry) -> None: ...

    async def delete_by_recipe_id(self, recipe_id: uuid.UUID) -> None: ...

    async def list_for_authors(self, author_ids: list[uuid.UUID]) -> list[FeedEntry]: ...
