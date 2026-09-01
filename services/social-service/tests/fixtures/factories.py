"""Shared test fixtures/factories -- Follow/FeedEntry builders and
in-memory fake port implementations (hexagonal-architecture SKILL.md:
"Application: unit tests using fake/in-memory implementations of ports,
not the real adapters")."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from domain.entities.follow import Follow
from domain.events.base import DomainEvent
from domain.ports.entitlement_check_port import EntitlementCheckUnavailableError
from domain.value_objects.feed_entry import FeedEntry

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def make_follow(**overrides) -> Follow:
    defaults = dict(
        follower_id=uuid.uuid4(),
        followee_id=uuid.uuid4(),
        now=NOW,
    )
    defaults.update(overrides)
    return Follow.create(**defaults)


def make_feed_entry(**overrides) -> FeedEntry:
    defaults = dict(
        recipe_id=uuid.uuid4(),
        author_id=uuid.uuid4(),
        title="Test Recipe",
        published_at=NOW,
    )
    defaults.update(overrides)
    return FeedEntry(**defaults)


class FakeFollowRepository:
    def __init__(self, seed: list[Follow] | None = None) -> None:
        self.by_id: dict[uuid.UUID, Follow] = {f.follow_id: f for f in (seed or [])}
        self.save_calls = 0
        self.delete_calls = 0
        self.get_calls = 0
        self.list_following_calls = 0
        self.list_followers_calls = 0

    async def get(self, follower_id: uuid.UUID, followee_id: uuid.UUID) -> Follow | None:
        self.get_calls += 1
        for follow in self.by_id.values():
            if follow.follower_id == follower_id and follow.followee_id == followee_id:
                return follow
        return None

    async def save(self, follow: Follow) -> None:
        self.save_calls += 1
        self.by_id[follow.follow_id] = follow

    async def delete(self, follow_id: uuid.UUID) -> None:
        self.delete_calls += 1
        self.by_id.pop(follow_id, None)

    async def list_following(self, follower_id: uuid.UUID) -> list[Follow]:
        self.list_following_calls += 1
        return [f for f in self.by_id.values() if f.follower_id == follower_id]

    async def list_followers(self, followee_id: uuid.UUID) -> list[Follow]:
        self.list_followers_calls += 1
        return [f for f in self.by_id.values() if f.followee_id == followee_id]


class FakeFeedRepository:
    def __init__(self, seed: list[FeedEntry] | None = None) -> None:
        self.by_recipe_id: dict[uuid.UUID, FeedEntry] = {e.recipe_id: e for e in (seed or [])}
        self.upsert_calls = 0
        self.delete_calls = 0
        self.list_for_authors_calls = 0

    async def upsert(self, entry: FeedEntry) -> None:
        self.upsert_calls += 1
        self.by_recipe_id[entry.recipe_id] = entry

    async def delete_by_recipe_id(self, recipe_id: uuid.UUID) -> None:
        self.delete_calls += 1
        self.by_recipe_id.pop(recipe_id, None)

    async def list_for_authors(self, author_ids: list[uuid.UUID]) -> list[FeedEntry]:
        self.list_for_authors_calls += 1
        author_id_set = set(author_ids)
        return [e for e in self.by_recipe_id.values() if e.author_id in author_id_set]


class FakeEntitlementCacheRepository:
    """In-memory `EntitlementCacheRepositoryPort` -- `seed` pre-populates
    `by_user` so a test can start from either a cache-hit or a genuine
    cache-miss (`get()` on an absent key returns `None`, matching the
    real Postgres adapter's contract)."""

    def __init__(self, seed: dict[uuid.UUID, bool] | None = None) -> None:
        self.by_user: dict[uuid.UUID, bool] = dict(seed) if seed else {}
        self.upsert_calls = 0

    async def get(self, user_id: uuid.UUID) -> bool | None:
        return self.by_user.get(user_id)

    async def upsert(self, user_id: uuid.UUID, entitled: bool, updated_at: datetime) -> None:
        self.upsert_calls += 1
        self.by_user[user_id] = entitled


class FakeEntitlementCheckPort:
    """In-memory `EntitlementCheckPort` -- set `raise_unavailable=True` to
    exercise the fail-safe (not-entitled) path a real circuit-open/
    transport failure would trigger."""

    def __init__(self, result: bool = False, raise_unavailable: bool = False) -> None:
        self.result = result
        self.raise_unavailable = raise_unavailable
        self.calls: list[uuid.UUID] = []

    async def check_entitlement(self, user_id: uuid.UUID) -> bool:
        self.calls.append(user_id)
        if self.raise_unavailable:
            raise EntitlementCheckUnavailableError("billing-service unavailable (fake).")
        return self.result


class FakeOutboxRepository:
    """In-memory `OutboxRepositoryPort` -- tracks which enqueued events
    have since been marked published, so `fetch_unpublished` can filter
    them out the same way the real Postgres query does."""

    def __init__(self) -> None:
        self.enqueued: list[DomainEvent] = []
        self.published_ids: set[uuid.UUID] = set()

    async def enqueue(self, event: DomainEvent) -> None:
        self.enqueued.append(event)

    async def fetch_unpublished(self, limit: int = 100) -> list[DomainEvent]:
        still_pending = [e for e in self.enqueued if e.event_id not in self.published_ids]
        return still_pending[:limit]

    async def mark_published(self, event_id: uuid.UUID) -> None:
        self.published_ids.add(event_id)


class _FakeEventIdLedger:
    """In-memory idempotency ledger shape shared by both
    `ProcessedEntitlementEventsRepositoryPort` and
    `ProcessedRecipeEventsRepositoryPort` -- the two real ports are
    structurally identical (`is_processed`/`mark_processed` keyed by
    `event_id` alone), so one fake implementation backs both aliases
    below instead of two hand-duplicated nine-line classes."""

    def __init__(self) -> None:
        self.processed: set[uuid.UUID] = set()

    async def is_processed(self, event_id: uuid.UUID) -> bool:
        return event_id in self.processed

    async def mark_processed(self, event_id: uuid.UUID) -> None:
        self.processed.add(event_id)


FakeProcessedEntitlementEventsRepository = _FakeEventIdLedger
FakeProcessedRecipeEventsRepository = _FakeEventIdLedger
