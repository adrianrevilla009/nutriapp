"""GET /api/v1/social/feed -- test-plan section 3. Feed entries are seeded
directly via the repository layer (there is no HTTP route to create one --
they only ever arrive by consuming recipe-service's `RecipePublished`,
implementation plan section 1.3), against the same testcontainers Postgres
`app_client` uses."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.postgres_feed_repository import PostgresFeedRepository
from tests.contract.http.conftest import auth_headers
from tests.fixtures.factories import make_feed_entry


async def _seed_feed_entry(db_engine, **overrides) -> uuid.UUID:
    entry = make_feed_entry(**overrides)
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresFeedRepository(session)
        await repo.upsert(entry)
        await session.commit()
    return entry.recipe_id


async def test_feed_returns_entries_from_followed_authors_only(app_client, db_engine):
    client, container = app_client
    container.entitlement_check.result = True
    viewer_id = uuid.uuid4()
    followed_author = uuid.uuid4()
    non_followed_author = uuid.uuid4()

    await client.post(
        "/api/v1/social/follows",
        json={"followee_id": str(followed_author)},
        headers=auth_headers(viewer_id),
    )
    followed_recipe_id = await _seed_feed_entry(db_engine, author_id=followed_author)
    await _seed_feed_entry(db_engine, author_id=non_followed_author)

    response = await client.get("/api/v1/social/feed", headers=auth_headers(viewer_id))

    assert response.status_code == 200
    recipe_ids = [item["recipe_id"] for item in response.json()["items"]]
    assert recipe_ids == [str(followed_recipe_id)]


async def test_feed_unentitled_user_returns_402(app_client):
    client, container = app_client
    container.entitlement_check.result = False

    response = await client.get("/api/v1/social/feed", headers=auth_headers(uuid.uuid4()))

    assert response.status_code == 402
    assert response.json()["code"] == "NOT_ENTITLED"


async def test_feed_unauthenticated_returns_401(app_client):
    client, _container = app_client
    response = await client.get("/api/v1/social/feed")
    assert response.status_code == 401
