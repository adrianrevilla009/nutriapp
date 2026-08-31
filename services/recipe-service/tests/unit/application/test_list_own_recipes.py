from __future__ import annotations

import uuid

from application.queries.list_own_recipes import ListOwnRecipesHandler, ListOwnRecipesQuery
from tests.fixtures.factories import FakeRecipeRepository, make_recipe


async def test_list_own_recipes_includes_drafts_excludes_other_users():
    owner_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    own_draft = make_recipe(user_id=owner_id)
    other_recipe = make_recipe(user_id=other_user_id)
    handler = ListOwnRecipesHandler(FakeRecipeRepository(seed=[own_draft, other_recipe]))

    results = await handler.handle(ListOwnRecipesQuery(user_id=owner_id))

    assert [r.recipe_id for r in results] == [own_draft.recipe_id]
