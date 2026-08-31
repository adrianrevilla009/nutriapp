from __future__ import annotations

import uuid

import pytest

from application.errors import NotEntitledError
from application.queries.search_published_recipes import (
    SearchPublishedRecipesHandler,
    SearchPublishedRecipesQuery,
)
from tests.fixtures.factories import (
    NOW,
    FakeEntitlementCacheRepository,
    FakeEntitlementCheckPort,
    FakeRecipeRepository,
    make_recipe,
)


async def test_entitled_search_returns_only_published_recipes():
    searcher_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    published = make_recipe(user_id=other_user_id, title="Pasta Bake").publish(NOW)
    draft_of_searcher = make_recipe(user_id=searcher_id, title="Pasta Secret Draft")
    recipes = FakeRecipeRepository(seed=[published, draft_of_searcher])
    cache = FakeEntitlementCacheRepository(seed={searcher_id: True})
    handler = SearchPublishedRecipesHandler(recipes, cache, FakeEntitlementCheckPort())

    results = await handler.handle(
        SearchPublishedRecipesQuery(user_id=searcher_id, query_text="pasta")
    )

    assert [r.recipe_id for r in results] == [published.recipe_id]


async def test_unentitled_search_rejected_before_any_repository_query():
    searcher_id = uuid.uuid4()

    class ExplodingRecipeRepository(FakeRecipeRepository):
        async def search_published(self, query: str):
            raise AssertionError("search_published must not be called for an unentitled user")

    recipes = ExplodingRecipeRepository()
    cache = FakeEntitlementCacheRepository(seed={searcher_id: False})
    handler = SearchPublishedRecipesHandler(recipes, cache, FakeEntitlementCheckPort())

    with pytest.raises(NotEntitledError):
        await handler.handle(SearchPublishedRecipesQuery(user_id=searcher_id, query_text="pasta"))
