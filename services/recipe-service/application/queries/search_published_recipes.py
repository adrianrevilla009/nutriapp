"""SearchPublishedRecipesHandler -- backs `GET /api/v1/recipes/search?q=...`.
Pro-gated: same cache-first/fallback entitlement pattern as
`PublishRecipeHandler`, checked before any repository query is attempted
(cheapest-check-first, test-plan section 1). Only ever returns published
recipes -- `RecipeRepositoryPort.search_published` is the sole read path,
never a draft/unpublished recipe leaks through, even the searching user's
own."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from application.entitlement_check import is_user_entitled
from application.errors import NotEntitledError
from domain.entities.recipe import Recipe
from domain.ports.entitlement_cache_repository_port import EntitlementCacheRepositoryPort
from domain.ports.entitlement_check_port import EntitlementCheckPort
from domain.ports.recipe_repository_port import RecipeRepositoryPort


@dataclass(frozen=True, slots=True)
class SearchPublishedRecipesQuery:
    user_id: uuid.UUID
    query_text: str


class SearchPublishedRecipesHandler:
    def __init__(
        self,
        recipes: RecipeRepositoryPort,
        entitlement_cache: EntitlementCacheRepositoryPort,
        entitlement_check: EntitlementCheckPort,
    ) -> None:
        self._recipes = recipes
        self._entitlement_cache = entitlement_cache
        self._entitlement_check = entitlement_check

    async def handle(self, query: SearchPublishedRecipesQuery) -> list[Recipe]:
        entitled = await is_user_entitled(
            query.user_id, self._entitlement_cache, self._entitlement_check
        )
        if not entitled:
            raise NotEntitledError("User is not entitled to search recipes.")
        return await self._recipes.search_published(query.query_text)
