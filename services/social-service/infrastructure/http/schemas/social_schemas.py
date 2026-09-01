"""Pydantic v2 request/response schemas -- infrastructure layer only
(api-conventions SKILL.md). The domain/application layers never import
Pydantic (ADR-0001)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from domain.entities.follow import Follow
from domain.value_objects.feed_entry import FeedEntry


class FollowRequest(BaseModel):
    followee_id: uuid.UUID


class FollowResponse(BaseModel):
    follow_id: uuid.UUID
    follower_id: uuid.UUID
    followee_id: uuid.UUID
    followed_at: datetime


class FollowListResponse(BaseModel):
    items: list[FollowResponse]


class FeedEntryResponse(BaseModel):
    recipe_id: uuid.UUID
    author_id: uuid.UUID
    title: str | None
    published_at: datetime


class FeedResponse(BaseModel):
    items: list[FeedEntryResponse]


def follow_to_response(follow: Follow) -> FollowResponse:
    return FollowResponse(
        follow_id=follow.follow_id,
        follower_id=follow.follower_id,
        followee_id=follow.followee_id,
        followed_at=follow.followed_at,
    )


def feed_entry_to_response(entry: FeedEntry) -> FeedEntryResponse:
    return FeedEntryResponse(
        recipe_id=entry.recipe_id,
        author_id=entry.author_id,
        title=entry.title,
        published_at=entry.published_at,
    )
