"""ListOwnRecipesHandler -- backs `GET /api/v1/recipes?mine=true`. Not
Pro-gated. Includes unpublished/draft recipes -- an author always sees
their own full list regardless of publish state."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.entities.recipe import Recipe
from domain.ports.recipe_repository_port import RecipeRepositoryPort


@dataclass(frozen=True, slots=True)
class ListOwnRecipesQuery:
    user_id: uuid.UUID


class ListOwnRecipesHandler:
    def __init__(self, recipes: RecipeRepositoryPort) -> None:
        self._recipes = recipes

    async def handle(self, query: ListOwnRecipesQuery) -> list[Recipe]:
        return await self._recipes.list_by_user_id(query.user_id)
