from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from application.errors import NotEntitledError
from application.queries.get_feed import GetFeedHandler, GetFeedQuery
from tests.fixtures.factories import (
    FakeEntitlementCacheRepository,
    FakeEntitlementCheckPort,
    FakeFeedRepository,
    FakeFollowRepository,
    make_feed_entry,
    make_follow,
)

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)
EARLIER = NOW - timedelta(days=1)
LATER = NOW + timedelta(days=1)


def _handler(feed, follows, cache, check):
    return GetFeedHandler(feed, follows, cache, check)


async def test_feed_contains_only_entries_from_followed_authors_with_published_recipes():
    viewer_id = uuid.uuid4()
    followed_with_recipe = uuid.uuid4()
    followed_without_recipe = uuid.uuid4()
    follows = FakeFollowRepository(
        seed=[
            make_follow(follower_id=viewer_id, followee_id=followed_with_recipe),
            make_follow(follower_id=viewer_id, followee_id=followed_without_recipe),
        ]
    )
    entry = make_feed_entry(author_id=followed_with_recipe, published_at=NOW)
    feed = FakeFeedRepository(seed=[entry])
    cache = FakeEntitlementCacheRepository(seed={viewer_id: True})
    check = FakeEntitlementCheckPort()
    handler = _handler(feed, follows, cache, check)

    results = await handler.handle(GetFeedQuery(user_id=viewer_id))

    assert [r.recipe_id for r in results] == [entry.recipe_id]


async def test_feed_ordered_newest_published_first():
    viewer_id = uuid.uuid4()
    author_a = uuid.uuid4()
    author_b = uuid.uuid4()
    follows = FakeFollowRepository(
        seed=[
            make_follow(follower_id=viewer_id, followee_id=author_a),
            make_follow(follower_id=viewer_id, followee_id=author_b),
        ]
    )
    older = make_feed_entry(author_id=author_a, published_at=EARLIER)
    newer = make_feed_entry(author_id=author_b, published_at=LATER)
    feed = FakeFeedRepository(seed=[older, newer])
    cache = FakeEntitlementCacheRepository(seed={viewer_id: True})
    check = FakeEntitlementCheckPort()
    handler = _handler(feed, follows, cache, check)

    results = await handler.handle(GetFeedQuery(user_id=viewer_id))

    assert [r.recipe_id for r in results] == [newer.recipe_id, older.recipe_id]


async def test_entry_from_non_followed_author_never_appears():
    viewer_id = uuid.uuid4()
    followed_author = uuid.uuid4()
    non_followed_author = uuid.uuid4()
    follows = FakeFollowRepository(
        seed=[make_follow(follower_id=viewer_id, followee_id=followed_author)]
    )
    non_followed_entry = make_feed_entry(author_id=non_followed_author, published_at=NOW)
    feed = FakeFeedRepository(seed=[non_followed_entry])
    cache = FakeEntitlementCacheRepository(seed={viewer_id: True})
    check = FakeEntitlementCheckPort()
    handler = _handler(feed, follows, cache, check)

    results = await handler.handle(GetFeedQuery(user_id=viewer_id))

    assert results == []


async def test_entitled_user_with_no_followed_authors_returns_empty_without_feed_query():
    viewer_id = uuid.uuid4()
    follows = FakeFollowRepository()
    feed = FakeFeedRepository(seed=[make_feed_entry()])
    cache = FakeEntitlementCacheRepository(seed={viewer_id: True})
    check = FakeEntitlementCheckPort()
    handler = _handler(feed, follows, cache, check)

    results = await handler.handle(GetFeedQuery(user_id=viewer_id))

    assert results == []
    assert feed.list_for_authors_calls == 0


async def test_unentitled_user_rejected_before_any_repository_query():
    viewer_id = uuid.uuid4()
    follows = FakeFollowRepository()
    feed = FakeFeedRepository()
    cache = FakeEntitlementCacheRepository(seed={viewer_id: False})
    check = FakeEntitlementCheckPort()
    handler = _handler(feed, follows, cache, check)

    with pytest.raises(NotEntitledError):
        await handler.handle(GetFeedQuery(user_id=viewer_id))

    assert follows.list_following_calls == 0
    assert feed.list_for_authors_calls == 0
