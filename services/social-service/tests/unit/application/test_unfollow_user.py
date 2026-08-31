from __future__ import annotations

import uuid

import pytest

from application.commands.unfollow_user import UnfollowUserCommand, UnfollowUserHandler
from application.errors import NotEntitledError
from tests.fixtures.factories import (
    NOW,
    FakeEntitlementCacheRepository,
    FakeEntitlementCheckPort,
    FakeFollowRepository,
    FakeOutboxRepository,
    make_follow,
)


def _handler(follows, cache, check, outbox):
    return UnfollowUserHandler(follows, cache, check, outbox, now_fn=lambda: NOW)


async def test_following_user_unfollows_hard_deletes_row_and_publishes():
    existing = make_follow()
    follows = FakeFollowRepository(seed=[existing])
    cache = FakeEntitlementCacheRepository(seed={existing.follower_id: True})
    check = FakeEntitlementCheckPort()
    outbox = FakeOutboxRepository()
    handler = _handler(follows, cache, check, outbox)

    await handler.handle(
        UnfollowUserCommand(
            follower_id=existing.follower_id, followee_id=existing.followee_id, correlation_id="c-1"
        )
    )

    assert follows.delete_calls == 1
    assert existing.follow_id not in follows.by_id
    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.event_type == "UserUnfollowed"
    assert event.payload["follow_id"] == str(existing.follow_id)
    assert event.payload["follower_id"] == str(existing.follower_id)
    assert event.payload["followee_id"] == str(existing.followee_id)


async def test_not_currently_following_is_idempotent_no_op_no_event():
    follower_id = uuid.uuid4()
    followee_id = uuid.uuid4()
    follows = FakeFollowRepository()
    cache = FakeEntitlementCacheRepository(seed={follower_id: True})
    check = FakeEntitlementCheckPort()
    outbox = FakeOutboxRepository()
    handler = _handler(follows, cache, check, outbox)

    await handler.handle(
        UnfollowUserCommand(follower_id=follower_id, followee_id=followee_id, correlation_id="c-2")
    )

    assert follows.delete_calls == 0
    assert outbox.enqueued == []


async def test_unentitled_user_rejected_before_any_repository_write():
    existing = make_follow()
    follows = FakeFollowRepository(seed=[existing])
    cache = FakeEntitlementCacheRepository(seed={existing.follower_id: False})
    check = FakeEntitlementCheckPort()
    outbox = FakeOutboxRepository()
    handler = _handler(follows, cache, check, outbox)

    with pytest.raises(NotEntitledError):
        await handler.handle(
            UnfollowUserCommand(
                follower_id=existing.follower_id,
                followee_id=existing.followee_id,
                correlation_id="c-3",
            )
        )

    assert follows.get_calls == 0
    assert follows.delete_calls == 0
    assert outbox.enqueued == []
