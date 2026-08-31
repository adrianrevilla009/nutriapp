from __future__ import annotations

import inspect
import uuid

import pytest

from application.commands.create_recipe import (
    CreateRecipeCommand,
    CreateRecipeHandler,
    CreateRecipeIngredientInput,
)
from application.errors import UnresolvableIngredientError
from tests.fixtures.factories import (
    NOW,
    FakeCatalogProductPort,
    FakeOutboxRepository,
    FakeRecipeRepository,
    make_resolved_product,
)


def test_command_signature_never_accepts_a_totals_parameter():
    """Structural guard (recipe-agent.md): computed totals are ALWAYS
    server-derived, never caller-supplied -- the command dataclass itself
    has no field that could carry one."""
    fields = {f for f in CreateRecipeCommand.__dataclass_fields__}
    assert not any("total" in f for f in fields)
    assert not any("macro" in f or "micronutrient" in f for f in fields)


def test_handle_signature_has_no_totals_parameter():
    signature = inspect.signature(CreateRecipeHandler.handle)
    assert "computed_totals" not in signature.parameters
    assert "totals" not in signature.parameters


async def test_all_ingredients_resolve_persists_recipe_with_computed_totals():
    product_id = uuid.uuid4()
    catalog = FakeCatalogProductPort(resolvable={product_id: make_resolved_product(product_id)})
    recipes = FakeRecipeRepository()
    outbox = FakeOutboxRepository()
    handler = CreateRecipeHandler(recipes, catalog, outbox, now_fn=lambda: NOW)

    command = CreateRecipeCommand(
        user_id=uuid.uuid4(),
        title="Omelette",
        instructions="Whisk and cook.",
        servings=2,
        ingredients=[
            CreateRecipeIngredientInput(catalog_product_id=product_id, quantity_grams=100)
        ],
        correlation_id="corr-1",
    )

    recipe = await handler.handle(command)

    assert recipes.save_calls == 1
    assert recipe.computed_totals.per_recipe.macros.calories_kcal == 100.0
    assert recipe.computed_totals.per_serving.macros.calories_kcal == 50.0

    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.event_type == "RecipeCreated"
    assert event.payload["recipe_id"] == str(recipe.recipe_id)
    # The published event's payload never carries user-suppliable totals.
    assert "computed_totals" not in event.payload
    assert "totals" not in event.payload


async def test_unresolvable_ingredient_blocks_creation_no_partial_recipe_no_event():
    unresolvable_id = uuid.uuid4()
    catalog = FakeCatalogProductPort(resolvable={})
    recipes = FakeRecipeRepository()
    outbox = FakeOutboxRepository()
    handler = CreateRecipeHandler(recipes, catalog, outbox, now_fn=lambda: NOW)

    command = CreateRecipeCommand(
        user_id=uuid.uuid4(),
        title="Bad Recipe",
        instructions="N/A",
        servings=1,
        ingredients=[
            CreateRecipeIngredientInput(catalog_product_id=unresolvable_id, quantity_grams=100)
        ],
        correlation_id="corr-2",
    )

    with pytest.raises(UnresolvableIngredientError):
        await handler.handle(command)

    assert recipes.save_calls == 0
    assert outbox.enqueued == []
