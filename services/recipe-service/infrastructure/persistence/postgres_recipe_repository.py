"""PostgresRecipeRepository -- implements RecipeRepositoryPort.
`ingredients`/`computed_totals` are stored as JSONB, serialized/
deserialized here only -- the domain layer never sees a JSON-shaped dict
(ADR-0001)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.recipe import Recipe
from domain.value_objects.nutrient_totals import MacroAmounts, NutrientTotals, RecipeNutrientTotals
from domain.value_objects.recipe_ingredient import RecipeIngredient
from domain.value_objects.servings import Servings
from infrastructure.persistence.models import RecipeModel


def _ingredients_to_json(ingredients: tuple[RecipeIngredient, ...]) -> list[dict[str, Any]]:
    return [
        {"catalog_product_id": str(i.catalog_product_id), "quantity_grams": i.quantity_grams}
        for i in ingredients
    ]


def _ingredients_from_json(raw: list[dict[str, Any]]) -> tuple[RecipeIngredient, ...]:
    return tuple(
        RecipeIngredient(
            catalog_product_id=uuid.UUID(i["catalog_product_id"]),
            quantity_grams=i["quantity_grams"],
        )
        for i in raw
    )


def _nutrient_totals_to_json(totals: NutrientTotals) -> dict[str, Any]:
    return {
        "macros": {
            "calories_kcal": totals.macros.calories_kcal,
            "protein_g": totals.macros.protein_g,
            "carbs_g": totals.macros.carbs_g,
            "fat_g": totals.macros.fat_g,
        },
        "macros_status": totals.macros_status,
        "micronutrients": dict(totals.micronutrients)
        if totals.micronutrients is not None
        else None,
        "micronutrients_status": totals.micronutrients_status,
    }


def _nutrient_totals_from_json(raw: dict[str, Any]) -> NutrientTotals:
    return NutrientTotals(
        macros=MacroAmounts(**raw["macros"]),
        macros_status=raw["macros_status"],
        micronutrients=raw["micronutrients"],
        micronutrients_status=raw["micronutrients_status"],
    )


def _computed_totals_to_json(totals: RecipeNutrientTotals) -> dict[str, Any]:
    return {
        "per_recipe": _nutrient_totals_to_json(totals.per_recipe),
        "per_serving": _nutrient_totals_to_json(totals.per_serving),
    }


def _computed_totals_from_json(raw: dict[str, Any]) -> RecipeNutrientTotals:
    return RecipeNutrientTotals(
        per_recipe=_nutrient_totals_from_json(raw["per_recipe"]),
        per_serving=_nutrient_totals_from_json(raw["per_serving"]),
    )


def _to_domain(row: RecipeModel) -> Recipe:
    return Recipe(
        recipe_id=row.recipe_id,
        user_id=row.user_id,
        title=row.title,
        instructions=row.instructions,
        servings=Servings(row.servings),
        ingredients=_ingredients_from_json(row.ingredients),
        computed_totals=_computed_totals_from_json(row.computed_totals),
        is_published=row.is_published,
        unpublished_at=row.unpublished_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PostgresRecipeRepository:
    """Implements domain.ports.recipe_repository_port.RecipeRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, recipe_id: uuid.UUID) -> Recipe | None:
        row = await self._session.get(RecipeModel, recipe_id)
        return _to_domain(row) if row is not None else None

    async def list_by_user_id(self, user_id: uuid.UUID) -> list[Recipe]:
        stmt = (
            select(RecipeModel)
            .where(RecipeModel.user_id == user_id)
            .order_by(RecipeModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [_to_domain(row) for row in result.scalars()]

    async def search_published(self, query: str) -> list[Recipe]:
        stmt = (
            select(RecipeModel)
            .where(RecipeModel.is_published.is_(True))
            .where(
                or_(
                    func.lower(RecipeModel.title).contains(query.lower()),
                    func.lower(RecipeModel.instructions).contains(query.lower()),
                )
            )
            .order_by(RecipeModel.updated_at.desc())
        )
        result = await self._session.execute(stmt)
        return [_to_domain(row) for row in result.scalars()]

    async def save(self, recipe: Recipe) -> None:
        row = await self._session.get(RecipeModel, recipe.recipe_id)
        if row is None:
            row = RecipeModel(recipe_id=recipe.recipe_id)
            self._session.add(row)
        row.user_id = recipe.user_id
        row.title = recipe.title
        row.instructions = recipe.instructions
        row.servings = int(recipe.servings)
        row.ingredients = _ingredients_to_json(recipe.ingredients)
        row.computed_totals = _computed_totals_to_json(recipe.computed_totals)
        row.is_published = recipe.is_published
        row.unpublished_at = recipe.unpublished_at
        row.created_at = recipe.created_at
        row.updated_at = recipe.updated_at
        await self._session.flush()
