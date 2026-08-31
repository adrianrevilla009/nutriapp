from __future__ import annotations

import uuid

from application.commands.unpublish_recipe import UnpublishRecipeCommand, UnpublishRecipeHandler
from tests.fixtures.factories import NOW, FakeOutboxRepository, FakeRecipeRepository, make_recipe


async def test_published_recipe_is_unpublished_never_hard_deleted_and_event_published():
    owner_id = uuid.uuid4()
    recipe = make_recipe(user_id=owner_id).publish(NOW)
    recipes = FakeRecipeRepository(seed=[recipe])
    outbox = FakeOutboxRepository()
    handler = UnpublishRecipeHandler(recipes, outbox, now_fn=lambda: NOW)

    result = await handler.handle(
        UnpublishRecipeCommand(
            recipe_id=recipe.recipe_id, user_id=owner_id, correlation_id="corr-1"
        )
    )

    assert result.is_published is False
    assert result.unpublished_at == NOW
    assert recipes.delete_calls == 0
    assert recipes.save_calls == 1
    assert len(outbox.enqueued) == 1
    assert outbox.enqueued[0].event_type == "RecipeUnpublished"


async def test_already_unpublished_recipe_is_idempotent_no_duplicate_event():
    owner_id = uuid.uuid4()
    recipe = make_recipe(user_id=owner_id).publish(NOW).unpublish(NOW)
    recipes = FakeRecipeRepository(seed=[recipe])
    outbox = FakeOutboxRepository()
    handler = UnpublishRecipeHandler(recipes, outbox, now_fn=lambda: NOW)

    await handler.handle(
        UnpublishRecipeCommand(
            recipe_id=recipe.recipe_id, user_id=owner_id, correlation_id="corr-2"
        )
    )

    assert outbox.enqueued == []


async def test_never_published_draft_succeeds_without_publishing_event():
    owner_id = uuid.uuid4()
    draft = make_recipe(user_id=owner_id)
    recipes = FakeRecipeRepository(seed=[draft])
    outbox = FakeOutboxRepository()
    handler = UnpublishRecipeHandler(recipes, outbox, now_fn=lambda: NOW)

    result = await handler.handle(
        UnpublishRecipeCommand(recipe_id=draft.recipe_id, user_id=owner_id, correlation_id="corr-3")
    )

    assert result.is_published is False
    assert outbox.enqueued == []
