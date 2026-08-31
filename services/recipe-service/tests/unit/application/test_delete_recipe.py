from __future__ import annotations

import uuid

from application.commands.delete_recipe import DeleteRecipeCommand, DeleteRecipeHandler
from tests.fixtures.factories import NOW, FakeOutboxRepository, FakeRecipeRepository, make_recipe


async def test_delete_published_recipe_soft_unpublishes_never_hard_deletes():
    owner_id = uuid.uuid4()
    recipe = make_recipe(user_id=owner_id).publish(NOW)
    recipes = FakeRecipeRepository(seed=[recipe])
    outbox = FakeOutboxRepository()
    handler = DeleteRecipeHandler(recipes, outbox, now_fn=lambda: NOW)

    result = await handler.handle(
        DeleteRecipeCommand(recipe_id=recipe.recipe_id, user_id=owner_id, correlation_id="corr-1")
    )

    assert result.is_published is False
    assert recipes.delete_calls == 0
    assert await recipes.get_by_id(recipe.recipe_id) is not None  # row retained
    assert len(outbox.enqueued) == 1
    assert outbox.enqueued[0].event_type == "RecipeUnpublished"


async def test_delete_never_published_draft_emits_no_event():
    owner_id = uuid.uuid4()
    draft = make_recipe(user_id=owner_id)
    recipes = FakeRecipeRepository(seed=[draft])
    outbox = FakeOutboxRepository()
    handler = DeleteRecipeHandler(recipes, outbox, now_fn=lambda: NOW)

    await handler.handle(
        DeleteRecipeCommand(recipe_id=draft.recipe_id, user_id=owner_id, correlation_id="corr-2")
    )

    assert outbox.enqueued == []
