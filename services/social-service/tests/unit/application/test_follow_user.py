from __future__ import annotations

import uuid

import pytest

from application.commands.follow_user import FollowUserCommand, FollowUserHandler
from application.errors import NotEntitledError
from domain.entities.follow import SelfFollowError
from tests.fixtures.factories import (
    NOW,
    FakeEntitlementCacheRepository,
    FakeEntitlementCheckPort,
    FakeFollowRepository,
    FakeOutboxRepository,
    make_follow,
)


def _handler(follows, cache, check, outbox):
    return FollowUserHandler(follows, cache, check, outbox, now_fn=lambda: NOW)


async def test_entitled_cache_hit_following_a_new_user_persists_and_publishes():
    follower_id = uuid.uuid4()
    followee_id = uuid.uuid4()
    follows = FakeFollowRepository()
    cache = FakeEntitlementCacheRepository(seed={follower_id: True})
    check = FakeEntitlementCheckPort()
    outbox = FakeOutboxRepository()
    handler = _handler(follows, cache, check, outbox)

    result = await handler.handle(
        FollowUserCommand(follower_id=follower_id, followee_id=followee_id, correlation_id="c-1")
    )

    assert result.follower_id == follower_id
    assert result.followee_id == followee_id
    assert follows.save_calls == 1
    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.event_type == "UserFollowed"
    assert event.payload["follow_id"] == str(result.follow_id)
    assert event.payload["follower_id"] == str(follower_id)
    assert event.payload["followee_id"] == str(followee_id)
    assert check.calls == []  # cache hit, fallback never called


async def test_self_follow_rejected_before_any_repository_write_no_event():
    user_id = uuid.uuid4()
    follows = FakeFollowRepository()
    cache = FakeEntitlementCacheRepository(seed={user_id: True})
    check = FakeEntitlementCheckPort()
    outbox = FakeOutboxRepository()
    handler = _handler(follows, cache, check, outbox)

    with pytest.raises(SelfFollowError):
        await handler.handle(
            FollowUserCommand(follower_id=user_id, followee_id=user_id, correlation_id="c-2")
        )

    assert follows.save_calls == 0
    assert follows.get_calls == 0
    assert outbox.enqueued == []


async def test_already_following_is_idempotent_no_duplicate_row_or_event():
    follower_id = uuid.uuid4()
    followee_id = uuid.uuid4()
    existing = make_follow(follower_id=follower_id, followee_id=followee_id)
    follows = FakeFollowRepository(seed=[existing])
    cache = FakeEntitlementCacheRepository(seed={follower_id: True})
    check = FakeEntitlementCheckPort()
    outbox = FakeOutboxRepository()
    handler = _handler(follows, cache, check, outbox)

    result = await handler.handle(
        FollowUserCommand(follower_id=follower_id, followee_id=followee_id, correlation_id="c-3")
    )

    assert result.follow_id == existing.follow_id
    assert follows.save_calls == 0
    assert len(outbox.enqueued) == 0


async def test_unentitled_cache_hit_rejected_before_any_repository_write():
    follower_id = uuid.uuid4()
    followee_id = uuid.uuid4()
    follows = FakeFollowRepository()
    cache = FakeEntitlementCacheRepository(seed={follower_id: False})
    check = FakeEntitlementCheckPort()
    outbox = FakeOutboxRepository()
    handler = _handler(follows, cache, check, outbox)

    with pytest.raises(NotEntitledError):
        await handler.handle(
            FollowUserCommand(
                follower_id=follower_id, followee_id=followee_id, correlation_id="c-4"
            )
        )

    assert follows.save_calls == 0
    assert follows.get_calls == 0
    assert outbox.enqueued == []


async def test_cache_miss_falls_back_true_proceeds_and_never_caches():
    follower_id = uuid.uuid4()
    followee_id = uuid.uuid4()
    follows = FakeFollowRepository()
    cache = FakeEntitlementCacheRepository(seed={})
    check = FakeEntitlementCheckPort(result=True)
    outbox = FakeOutboxRepository()
    handler = _handler(follows, cache, check, outbox)

    result = await handler.handle(
        FollowUserCommand(follower_id=follower_id, followee_id=followee_id, correlation_id="c-5")
    )

    assert result.follower_id == follower_id
    assert check.calls == [follower_id]
    assert cache.upsert_calls == 0


async def test_cache_miss_falls_back_false_rejects_and_never_caches():
    follower_id = uuid.uuid4()
    followee_id = uuid.uuid4()
    follows = FakeFollowRepository()
    cache = FakeEntitlementCacheRepository(seed={})
    check = FakeEntitlementCheckPort(result=False)
    outbox = FakeOutboxRepository()
    handler = _handler(follows, cache, check, outbox)

    with pytest.raises(NotEntitledError):
        await handler.handle(
            FollowUserCommand(
                follower_id=follower_id, followee_id=followee_id, correlation_id="c-6"
            )
        )

    assert cache.upsert_calls == 0
    assert follows.save_calls == 0
    assert outbox.enqueued == []
