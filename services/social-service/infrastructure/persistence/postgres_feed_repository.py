"""PostgresFeedRepository -- implements FeedRepositoryPort. `upsert` is
keyed by `recipe_id` (one row per recipe); `list_for_authors` is the join
half of `GET /feed` -- callers pass the caller's own followed author ids,
never an unfiltered query."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.value_objects.feed_entry import FeedEntry
from infrastructure.persistence.models import FeedEntryModel


def _to_domain(row: FeedEntryModel) -> FeedEntry:
    return FeedEntry(
        recipe_id=row.recipe_id,
        author_id=row.author_id,
        title=row.title,
        published_at=row.published_at,
    )


class PostgresFeedRepository:
    """Implements domain.ports.feed_repository_port.FeedRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, entry: FeedEntry) -> None:
        row = await self._session.get(FeedEntryModel, entry.recipe_id)
        if row is None:
            row = FeedEntryModel(recipe_id=entry.recipe_id)
            self._session.add(row)
        row.author_id = entry.author_id
        row.title = entry.title
        row.published_at = entry.published_at
        await self._session.flush()

    async def delete_by_recipe_id(self, recipe_id: uuid.UUID) -> None:
        row = await self._session.get(FeedEntryModel, recipe_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()

    async def list_for_authors(self, author_ids: list[uuid.UUID]) -> list[FeedEntry]:
        if not author_ids:
            return []
        stmt = (
            select(FeedEntryModel)
            .where(FeedEntryModel.author_id.in_(author_ids))
            .order_by(FeedEntryModel.published_at.desc())
        )
        result = await self._session.execute(stmt)
        return [_to_domain(row) for row in result.scalars()]
