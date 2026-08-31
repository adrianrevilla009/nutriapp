from __future__ import annotations

import uuid

import pytest

from application.commands.publish_recipe import PublishRecipeCommand, PublishRecipeHandler
from application.errors import NotEntitledError, UnresolvableIngredientError
from domain.value_objects.recipe_ingredient import RecipeIngredient
from tests.fixtures.factories import (
    NOW,
    FakeCatalogProductPort,
    FakeEntitlementCacheRepository,
    FakeEntitlementCheckPort,
    FakeOutboxRepository,
    FakeRecipeRepository,
    make_recipe,
    make_resolved_product,
)


def _handler(recipes, catalog, cache, check, outbox):
    return PublishRecipeHandler(recipes, catalog, cache, check, outbox, now_fn=lambda: NOW)


async def test_entitled_cache_hit_all_ingredients_resolve_publishes():
    product_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    recipe = make_recipe(user_id=owner_id, ingredients=(RecipeIngredient(product_id, 100),))
    recipes = FakeRecipeRepository(seed=[recipe])
    catalog = FakeCatalogProductPort(resolvable={product_id: make_resolved_product(product_id)})
    cache = FakeEntitlementCacheRepository(seed={owner_id: True})
    check = FakeEntitlementCheckPort()
    outbox = FakeOutboxRepository()
    handler = _handler(recipes, catalog, cache, check, outbox)

    result = await handler.handle(
        PublishRecipeCommand(recipe_id=recipe.recipe_id, user_id=owner_id, correlation_id="corr-1")
    )

    assert result.is_published is True
    assert len(outbox.enqueued) == 1
    assert outbox.enqueued[0].event_type == "RecipePublished"
    assert check.calls == []  # cache hit, fallback never called


async def test_entitled_but_unresolvable_ingredient_blocks_publish_no_event():
    product_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    recipe = make_recipe(user_id=owner_id, ingredients=(RecipeIngredient(product_id, 100),))
    recipes = FakeRecipeRepository(seed=[recipe])
    catalog = FakeCatalogProductPort(resolvable={})  # product removed from catalog since creation
    cache = FakeEntitlementCacheRepository(seed={owner_id: True})
    check = FakeEntitlementCheckPort()
    outbox = FakeOutboxRepository()
    handler = _handler(recipes, catalog, cache, check, outbox)

    with pytest.raises(UnresolvableIngredientError):
        await handler.handle(
            PublishRecipeCommand(
                recipe_id=recipe.recipe_id, user_id=owner_id, correlation_id="corr-2"
            )
        )

    persisted = await recipes.get_by_id(recipe.recipe_id)
    assert persisted.is_published is False
    assert outbox.enqueued == []


async def test_unentitled_cache_hit_rejected_before_any_ingredient_resolution_call():
    product_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    recipe = make_recipe(user_id=owner_id, ingredients=(RecipeIngredient(product_id, 100),))
    recipes = FakeRecipeRepository(seed=[recipe])
    catalog = FakeCatalogProductPort(resolvable={product_id: make_resolved_product(product_id)})
    cache = FakeEntitlementCacheRepository(seed={owner_id: False})
    check = FakeEntitlementCheckPort()
    outbox = FakeOutboxRepository()
    handler = _handler(recipes, catalog, cache, check, outbox)

    with pytest.raises(NotEntitledError):
        await handler.handle(
            PublishRecipeCommand(
                recipe_id=recipe.recipe_id, user_id=owner_id, correlation_id="corr-3"
            )
        )

    assert catalog.calls == []  # entitlement checked first, cheapest check wins
    assert outbox.enqueued == []


async def test_cache_miss_falls_back_to_entitlement_check_true_proceeds_and_never_caches():
    product_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    recipe = make_recipe(user_id=owner_id, ingredients=(RecipeIngredient(product_id, 100),))
    recipes = FakeRecipeRepository(seed=[recipe])
    catalog = FakeCatalogProductPort(resolvable={product_id: make_resolved_product(product_id)})
    cache = FakeEntitlementCacheRepository(seed={})  # no row -> cache miss
    check = FakeEntitlementCheckPort(result=True)
    outbox = FakeOutboxRepository()
    handler = _handler(recipes, catalog, cache, check, outbox)

    result = await handler.handle(
        PublishRecipeCommand(recipe_id=recipe.recipe_id, user_id=owner_id, correlation_id="corr-4")
    )

    assert result.is_published is True
    assert check.calls == [owner_id]
    assert cache.upsert_calls == 0  # fallback result is NEVER written back into the cache


async def test_cache_miss_falls_back_to_entitlement_check_false_rejects_and_never_caches():
    product_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    recipe = make_recipe(user_id=owner_id, ingredients=(RecipeIngredient(product_id, 100),))
    recipes = FakeRecipeRepository(seed=[recipe])
    catalog = FakeCatalogProductPort(resolvable={product_id: make_resolved_product(product_id)})
    cache = FakeEntitlementCacheRepository(seed={})
    check = FakeEntitlementCheckPort(result=False)
    outbox = FakeOutboxRepository()
    handler = _handler(recipes, catalog, cache, check, outbox)

    with pytest.raises(NotEntitledError):
        await handler.handle(
            PublishRecipeCommand(
                recipe_id=recipe.recipe_id, user_id=owner_id, correlation_id="corr-5"
            )
        )

    assert cache.upsert_calls == 0
    assert outbox.enqueued == []
