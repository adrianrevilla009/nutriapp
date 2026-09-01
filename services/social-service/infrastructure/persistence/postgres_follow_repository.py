"""PostgresFollowRepository -- implements FollowRepositoryPort. `delete`
is a genuine hard row delete (implementation plan section 1, confirmed
deviation from recipe-service's soft-delete-only convention)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.follow import Follow
from infrastructure.persistence.models import FollowModel


def _to_domain(row: FollowModel) -> Follow:
    return Follow(
        follow_id=row.follow_id,
        follower_id=row.follower_id,
        followee_id=row.followee_id,
        followed_at=row.followed_at,
    )


class PostgresFollowRepository:
    """Implements domain.ports.follow_repository_port.FollowRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, follower_id: uuid.UUID, followee_id: uuid.UUID) -> Follow | None:
        stmt = select(FollowModel).where(
            FollowModel.follower_id == follower_id, FollowModel.followee_id == followee_id
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_domain(row) if row is not None else None

    async def save(self, follow: Follow) -> None:
        row = FollowModel(
            follow_id=follow.follow_id,
            follower_id=follow.follower_id,
            followee_id=follow.followee_id,
            followed_at=follow.followed_at,
        )
        self._session.add(row)
        await self._session.flush()

    async def delete(self, follow_id: uuid.UUID) -> None:
        row = await self._session.get(FollowModel, follow_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()

    async def list_following(self, follower_id: uuid.UUID) -> list[Follow]:
        stmt = (
            select(FollowModel)
            .where(FollowModel.follower_id == follower_id)
            .order_by(FollowModel.followed_at.desc())
        )
        result = await self._session.execute(stmt)
        return [_to_domain(row) for row in result.scalars()]

    async def list_followers(self, followee_id: uuid.UUID) -> list[Follow]:
        stmt = (
            select(FollowModel)
            .where(FollowModel.followee_id == followee_id)
            .order_by(FollowModel.followed_at.desc())
        )
        result = await self._session.execute(stmt)
        return [_to_domain(row) for row in result.scalars()]
