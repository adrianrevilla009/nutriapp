from __future__ import annotations

import uuid

import pytest

from application.errors import RecipeNotFoundError
from application.queries.get_recipe import GetRecipeHandler, GetRecipeQuery
from tests.fixtures.factories import FakeRecipeRepository, make_recipe


async def test_owner_can_read_own_draft_recipe():
    owner_id = uuid.uuid4()
    recipe = make_recipe(user_id=owner_id)
    handler = GetRecipeHandler(FakeRecipeRepository(seed=[recipe]))

    result = await handler.handle(GetRecipeQuery(recipe_id=recipe.recipe_id, user_id=owner_id))
    assert result.recipe_id == recipe.recipe_id


async def test_another_users_recipe_raises_not_found():
    owner_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    recipe = make_recipe(user_id=owner_id)
    handler = GetRecipeHandler(FakeRecipeRepository(seed=[recipe]))

    with pytest.raises(RecipeNotFoundError):
        await handler.handle(GetRecipeQuery(recipe_id=recipe.recipe_id, user_id=other_user_id))


async def test_nonexistent_recipe_raises_not_found():
    handler = GetRecipeHandler(FakeRecipeRepository())
    with pytest.raises(RecipeNotFoundError):
        await handler.handle(GetRecipeQuery(recipe_id=uuid.uuid4(), user_id=uuid.uuid4()))
