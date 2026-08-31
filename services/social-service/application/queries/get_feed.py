"""GetFeedHandler -- backs `GET /api/v1/social/feed`. Pro-gated: same
cache-first/fallback entitlement pattern as `FollowUserHandler`, checked
before any `FeedRepositoryPort`/`FollowRepositoryPort` query is attempted
(cheapest-check-first, test-plan section 1). Fan-out-on-read
(implementation plan section 1.3): joins the caller's own `follows` table
against `feed_entries`, so an entry from a non-followed author never
appears -- join correctness, not just "the row exists somewhere"."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from application.entitlement_check import is_user_entitled
from application.errors import NotEntitledError
from domain.ports.entitlement_cache_repository_port import EntitlementCacheRepositoryPort
from domain.ports.entitlement_check_port import EntitlementCheckPort
from domain.ports.feed_repository_port import FeedRepositoryPort
from domain.ports.follow_repository_port import FollowRepositoryPort
from domain.value_objects.feed_entry import FeedEntry


@dataclass(frozen=True, slots=True)
class GetFeedQuery:
    user_id: uuid.UUID


class GetFeedHandler:
    def __init__(
        self,
        feed: FeedRepositoryPort,
        follows: FollowRepositoryPort,
        entitlement_cache: EntitlementCacheRepositoryPort,
        entitlement_check: EntitlementCheckPort,
    ) -> None:
        self._feed = feed
        self._follows = follows
        self._entitlement_cache = entitlement_cache
        self._entitlement_check = entitlement_check

    async def handle(self, query: GetFeedQuery) -> list[FeedEntry]:
        entitled = await is_user_entitled(
            query.user_id, self._entitlement_cache, self._entitlement_check
        )
        if not entitled:
            raise NotEntitledError("User is not entitled to view the activity feed.")

        following = await self._follows.list_following(query.user_id)
        author_ids = [f.followee_id for f in following]
        if not author_ids:
            return []

        entries = await self._feed.list_for_authors(author_ids)
        return sorted(entries, key=lambda e: e.published_at, reverse=True)
