"""GetRecipeHandler -- backs `GET /api/v1/recipes/{recipe_id}`. Not
Pro-gated. Same never-leak-existence shape as `UpdateRecipeHandler`."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from application.errors import RecipeNotFoundError
from domain.entities.recipe import Recipe
from domain.ports.recipe_repository_port import RecipeRepositoryPort


@dataclass(frozen=True, slots=True)
class GetRecipeQuery:
    recipe_id: uuid.UUID
    user_id: uuid.UUID


class GetRecipeHandler:
    def __init__(self, recipes: RecipeRepositoryPort) -> None:
        self._recipes = recipes

    async def handle(self, query: GetRecipeQuery) -> Recipe:
        recipe = await self._recipes.get_by_id(query.recipe_id)
        if recipe is None or recipe.user_id != query.user_id:
            raise RecipeNotFoundError(f"Recipe {query.recipe_id} not found.")
        return recipe
