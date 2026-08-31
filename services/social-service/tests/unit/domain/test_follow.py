from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from domain.entities.follow import Follow, SelfFollowError

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def test_create_builds_a_valid_follow():
    follower_id = uuid.uuid4()
    followee_id = uuid.uuid4()
    follow = Follow.create(follower_id=follower_id, followee_id=followee_id, now=NOW)
    assert follow.follower_id == follower_id
    assert follow.followee_id == followee_id
    assert follow.followed_at == NOW
    assert isinstance(follow.follow_id, uuid.UUID)


def test_self_follow_rejected_via_create():
    user_id = uuid.uuid4()
    with pytest.raises(SelfFollowError):
        Follow.create(follower_id=user_id, followee_id=user_id, now=NOW)


def test_self_follow_rejected_via_direct_construction():
    """Structural guard -- fires from __post_init__ regardless of
    construction path, not only Follow.create."""
    user_id = uuid.uuid4()
    with pytest.raises(SelfFollowError):
        Follow(follow_id=uuid.uuid4(), follower_id=user_id, followee_id=user_id, followed_at=NOW)


def test_two_different_users_produce_distinct_follow_ids():
    follower_id = uuid.uuid4()
    followee_id = uuid.uuid4()
    first = Follow.create(follower_id=follower_id, followee_id=followee_id, now=NOW)
    second = Follow.create(follower_id=follower_id, followee_id=followee_id, now=NOW)
    assert first.follow_id != second.follow_id
