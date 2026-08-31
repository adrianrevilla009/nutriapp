"""Pydantic v2 request/response schemas -- infrastructure layer only
(api-conventions SKILL.md). The domain/application layers never import
Pydantic (ADR-0001). Field-level validation here (e.g. `quantity_grams
gt=0`) is a fast-fail UX nicety at the edge; the domain value objects
(`RecipeIngredient`/`Servings`) remain the actual source of truth and are
re-validated regardless (never trust the edge alone)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from domain.entities.recipe import Recipe
from domain.value_objects.nutrient_totals import NutrientTotals


class RecipeIngredientRequest(BaseModel):
    catalog_product_id: uuid.UUID
    quantity_grams: float = Field(..., gt=0)


class CreateRecipeRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    instructions: str = Field(..., min_length=1)
    servings: int = Field(..., gt=0)
    ingredients: list[RecipeIngredientRequest] = Field(default_factory=list)


class UpdateRecipeRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    instructions: str = Field(..., min_length=1)
    servings: int = Field(..., gt=0)
    ingredients: list[RecipeIngredientRequest] = Field(default_factory=list)


class MacroAmountsResponse(BaseModel):
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


class NutrientTotalsResponse(BaseModel):
    macros: MacroAmountsResponse
    macros_status: Literal["available", "partial", "unavailable"]
    micronutrients: dict[str, float | None] | None
    micronutrients_status: Literal["available", "partial", "unavailable"]


class RecipeNutrientTotalsResponse(BaseModel):
    per_recipe: NutrientTotalsResponse
    per_serving: NutrientTotalsResponse


class RecipeIngredientResponse(BaseModel):
    catalog_product_id: uuid.UUID
    quantity_grams: float


class RecipeResponse(BaseModel):
    recipe_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    instructions: str
    servings: int
    ingredients: list[RecipeIngredientResponse]
    computed_totals: RecipeNutrientTotalsResponse
    is_published: bool
    unpublished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RecipeListResponse(BaseModel):
    items: list[RecipeResponse]


def _nutrient_totals_to_response(totals: NutrientTotals) -> NutrientTotalsResponse:
    return NutrientTotalsResponse(
        macros=MacroAmountsResponse(
            calories_kcal=totals.macros.calories_kcal,
            protein_g=totals.macros.protein_g,
            carbs_g=totals.macros.carbs_g,
            fat_g=totals.macros.fat_g,
        ),
        macros_status=totals.macros_status,
        micronutrients=dict(totals.micronutrients) if totals.micronutrients is not None else None,
        micronutrients_status=totals.micronutrients_status,
    )


def recipe_to_response(recipe: Recipe) -> RecipeResponse:
    return RecipeResponse(
        recipe_id=recipe.recipe_id,
        user_id=recipe.user_id,
        title=recipe.title,
        instructions=recipe.instructions,
        servings=int(recipe.servings),
        ingredients=[
            RecipeIngredientResponse(
                catalog_product_id=i.catalog_product_id, quantity_grams=i.quantity_grams
            )
            for i in recipe.ingredients
        ],
        computed_totals=RecipeNutrientTotalsResponse(
            per_recipe=_nutrient_totals_to_response(recipe.computed_totals.per_recipe),
            per_serving=_nutrient_totals_to_response(recipe.computed_totals.per_serving),
        ),
        is_published=recipe.is_published,
        unpublished_at=recipe.unpublished_at,
        created_at=recipe.created_at,
        updated_at=recipe.updated_at,
    )
