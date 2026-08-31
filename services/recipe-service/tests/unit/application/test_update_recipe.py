from __future__ import annotations

import uuid

import pytest

from application.commands.update_recipe import (
    UpdateRecipeCommand,
    UpdateRecipeHandler,
    UpdateRecipeIngredientInput,
)
from application.errors import RecipeNotFoundError
from tests.fixtures.factories import (
    NOW,
    FakeCatalogProductPort,
    FakeOutboxRepository,
    FakeRecipeRepository,
    make_recipe,
    make_resolved_product,
)


async def test_valid_update_recomputes_totals_and_publishes_once():
    product_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    recipe = make_recipe(user_id=owner_id)
    catalog = FakeCatalogProductPort(resolvable={product_id: make_resolved_product(product_id)})
    recipes = FakeRecipeRepository(seed=[recipe])
    outbox = FakeOutboxRepository()
    handler = UpdateRecipeHandler(recipes, catalog, outbox, now_fn=lambda: NOW)

    command = UpdateRecipeCommand(
        recipe_id=recipe.recipe_id,
        user_id=owner_id,
        title="Updated Title",
        instructions="New steps.",
        servings=1,
        ingredients=[
            UpdateRecipeIngredientInput(catalog_product_id=product_id, quantity_grams=100)
        ],
        correlation_id="corr-1",
    )

    updated = await handler.handle(command)

    assert updated.title == "Updated Title"
    assert updated.computed_totals.per_recipe.macros.calories_kcal == 100.0
    assert recipes.save_calls == 1
    assert len(outbox.enqueued) == 1
    assert outbox.enqueued[0].event_type == "RecipeUpdated"


async def test_editing_another_users_recipe_raises_not_found_no_write():
    owner_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    recipe = make_recipe(user_id=owner_id)
    catalog = FakeCatalogProductPort()
    recipes = FakeRecipeRepository(seed=[recipe])
    outbox = FakeOutboxRepository()
    handler = UpdateRecipeHandler(recipes, catalog, outbox, now_fn=lambda: NOW)

    command = UpdateRecipeCommand(
        recipe_id=recipe.recipe_id,
        user_id=other_user_id,
        title="Hijacked",
        instructions="N/A",
        servings=1,
        ingredients=[],
        correlation_id="corr-2",
    )

    with pytest.raises(RecipeNotFoundError):
        await handler.handle(command)

    assert recipes.save_calls == 0
    assert outbox.enqueued == []


async def test_editing_a_nonexistent_recipe_raises_not_found():
    recipes = FakeRecipeRepository()
    handler = UpdateRecipeHandler(
        recipes, FakeCatalogProductPort(), FakeOutboxRepository(), now_fn=lambda: NOW
    )

    command = UpdateRecipeCommand(
        recipe_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="N/A",
        instructions="N/A",
        servings=1,
        ingredients=[],
        correlation_id="corr-3",
    )

    with pytest.raises(RecipeNotFoundError):
        await handler.handle(command)
