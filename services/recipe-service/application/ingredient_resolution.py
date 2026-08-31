"""Shared ingredient-resolution helper -- used by `CreateRecipeHandler`,
`UpdateRecipeHandler` (need the resolved products' nutrition data to
compute totals) and `PublishRecipeHandler` (only needs to verify every
ingredient still resolves, re-checked fresh at publish time -- never
trusted from creation time, recipe-agent.md).

Resolves every ingredient BEFORE any write happens: an unresolvable
ingredient partway through the list must abort with no partial recipe
persisted and no event published (test-plan section 1).
"""

from __future__ import annotations

from application.errors import UnresolvableIngredientError
from domain.ports.catalog_product_port import CatalogProductPort, ResolvedIngredientProduct
from domain.value_objects.recipe_ingredient import RecipeIngredient


async def resolve_all_ingredients(
    ingredients: tuple[RecipeIngredient, ...], catalog_products: CatalogProductPort
) -> list[ResolvedIngredientProduct]:
    resolved: list[ResolvedIngredientProduct] = []
    for ingredient in ingredients:
        product = await catalog_products.get_product(ingredient.catalog_product_id)
        if product is None:
            raise UnresolvableIngredientError(
                f"catalog_product_id {ingredient.catalog_product_id} does not resolve to a "
                "real catalog-service product."
            )
        resolved.append(product)
    return resolved
