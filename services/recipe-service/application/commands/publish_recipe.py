"""PublishRecipeHandler -- backs `POST /api/v1/recipes/{recipe_id}/publish`.
Pro-gated (implementation plan section 1.4): entitlement is checked
BEFORE ingredient re-resolution -- cheapest check wins, and an unentitled
user's request never triggers a single `catalog-service` call
(test-plan section 1's explicit assertion). Blocks publish if any
ingredient no longer resolves (recipe-agent.md: never publish incomplete
data) -- re-verified fresh here, never trusted from creation/update time.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from application.entitlement_check import is_user_entitled
from application.errors import NotEntitledError, RecipeNotFoundError
from application.ingredient_resolution import resolve_all_ingredients
from domain.entities.recipe import Recipe
from domain.events.recipe_published import build_recipe_published_event
from domain.ports.catalog_product_port import CatalogProductPort
from domain.ports.entitlement_cache_repository_port import EntitlementCacheRepositoryPort
from domain.ports.entitlement_check_port import EntitlementCheckPort
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.ports.recipe_repository_port import RecipeRepositoryPort


@dataclass(frozen=True, slots=True)
class PublishRecipeCommand:
    recipe_id: uuid.UUID
    user_id: uuid.UUID
    correlation_id: str


class PublishRecipeHandler:
    def __init__(
        self,
        recipes: RecipeRepositoryPort,
        catalog_products: CatalogProductPort,
        entitlement_cache: EntitlementCacheRepositoryPort,
        entitlement_check: EntitlementCheckPort,
        outbox: OutboxRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._recipes = recipes
        self._catalog_products = catalog_products
        self._entitlement_cache = entitlement_cache
        self._entitlement_check = entitlement_check
        self._outbox = outbox
        self._now_fn = now_fn

    async def handle(self, command: PublishRecipeCommand) -> Recipe:
        recipe = await self._recipes.get_by_id(command.recipe_id)
        if recipe is None or recipe.user_id != command.user_id:
            raise RecipeNotFoundError(f"Recipe {command.recipe_id} not found.")

        entitled = await is_user_entitled(
            command.user_id, self._entitlement_cache, self._entitlement_check
        )
        if not entitled:
            raise NotEntitledError("User is not entitled to publish recipes.")

        # Re-verified fresh, never trusted from creation/update time -- a
        # product could have been removed from catalog-service since.
        await resolve_all_ingredients(recipe.ingredients, self._catalog_products)

        published = recipe.publish(self._now_fn())
        await self._recipes.save(published)
        await self._outbox.enqueue(
            build_recipe_published_event(
                recipe_id=published.recipe_id,
                user_id=published.user_id,
                correlation_id=command.correlation_id,
            )
        )
        return published
