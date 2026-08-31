"""Recipe authoring/publishing routes -- `POST /api/v1/recipes`,
`PATCH /api/v1/recipes/{recipe_id}`, `GET /api/v1/recipes/{recipe_id}`,
`GET /api/v1/recipes?mine=true`, `POST /api/v1/recipes/{recipe_id}/publish`,
`POST /api/v1/recipes/{recipe_id}/unpublish`,
`DELETE /api/v1/recipes/{recipe_id}` (implementation plan section 1).
JWT-authenticated via packages/shared-contracts' centralized dependency.
Only `/publish` is Pro-gated -- authoring/reading/unpublishing/deleting
your own recipe is free (recipe-agent.md).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.create_recipe import (
    CreateRecipeCommand,
    CreateRecipeHandler,
    CreateRecipeIngredientInput,
)
from application.commands.delete_recipe import DeleteRecipeCommand, DeleteRecipeHandler
from application.commands.publish_recipe import PublishRecipeCommand, PublishRecipeHandler
from application.commands.unpublish_recipe import UnpublishRecipeCommand, UnpublishRecipeHandler
from application.commands.update_recipe import (
    UpdateRecipeCommand,
    UpdateRecipeHandler,
    UpdateRecipeIngredientInput,
)
from application.queries.get_recipe import GetRecipeHandler, GetRecipeQuery
from application.queries.list_own_recipes import ListOwnRecipesHandler, ListOwnRecipesQuery
from infrastructure.composition_root import Container, build_repositories
from infrastructure.http.dependencies import (
    get_authenticated_user_id,
    get_container,
    get_correlation_id,
    get_session,
)
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.recipe_schemas import (
    CreateRecipeRequest,
    RecipeListResponse,
    RecipeResponse,
    UpdateRecipeRequest,
    recipe_to_response,
)

router = APIRouter(prefix="/api/v1/recipes", tags=["recipes"])


@router.post(
    "",
    response_model=RecipeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Author a new recipe",
)
async def create_recipe(
    body: CreateRecipeRequest,
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[Container, Depends(get_container)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
) -> RecipeResponse | JSONResponse:
    recipes, _cache, _processed, outbox = build_repositories(session)
    handler = CreateRecipeHandler(recipes, container.catalog_products, outbox)
    try:
        recipe = await handler.handle(
            CreateRecipeCommand(
                user_id=user_id,
                title=body.title,
                instructions=body.instructions,
                servings=body.servings,
                ingredients=[
                    CreateRecipeIngredientInput(
                        catalog_product_id=i.catalog_product_id, quantity_grams=i.quantity_grams
                    )
                    for i in body.ingredients
                ],
                correlation_id=correlation_id,
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return recipe_to_response(recipe)


@router.patch("/{recipe_id}", response_model=RecipeResponse, summary="Edit your own recipe")
async def update_recipe(
    recipe_id: uuid.UUID,
    body: UpdateRecipeRequest,
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[Container, Depends(get_container)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
) -> RecipeResponse | JSONResponse:
    recipes, _cache, _processed, outbox = build_repositories(session)
    handler = UpdateRecipeHandler(recipes, container.catalog_products, outbox)
    try:
        recipe = await handler.handle(
            UpdateRecipeCommand(
                recipe_id=recipe_id,
                user_id=user_id,
                title=body.title,
                instructions=body.instructions,
                servings=body.servings,
                ingredients=[
                    UpdateRecipeIngredientInput(
                        catalog_product_id=i.catalog_product_id, quantity_grams=i.quantity_grams
                    )
                    for i in body.ingredients
                ],
                correlation_id=correlation_id,
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return recipe_to_response(recipe)


@router.get(
    "/{recipe_id}", response_model=RecipeResponse, summary="Read your own recipe (including drafts)"
)
async def get_recipe(
    recipe_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RecipeResponse | JSONResponse:
    recipes, _cache, _processed, _outbox = build_repositories(session)
    handler = GetRecipeHandler(recipes)
    try:
        recipe = await handler.handle(GetRecipeQuery(recipe_id=recipe_id, user_id=user_id))
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return recipe_to_response(recipe)


@router.get(
    "", response_model=RecipeListResponse, summary="List your own recipes, including drafts"
)
async def list_own_recipes(
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    mine: Annotated[
        bool, Query(description="Must be true -- only own-recipe listing is supported.")
    ] = True,
) -> RecipeListResponse | JSONResponse:
    recipes, _cache, _processed, _outbox = build_repositories(session)
    handler = ListOwnRecipesHandler(recipes)
    try:
        results = await handler.handle(ListOwnRecipesQuery(user_id=user_id))
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return RecipeListResponse(items=[recipe_to_response(r) for r in results])


@router.post(
    "/{recipe_id}/publish",
    response_model=RecipeResponse,
    summary="Publish a recipe to cross-user search (Pro-gated)",
    description="Entitlement is checked before any ingredient re-resolution call. Blocks "
    "publish if any ingredient no longer resolves against catalog-service.",
)
async def publish_recipe(
    recipe_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[Container, Depends(get_container)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
) -> RecipeResponse | JSONResponse:
    recipes, cache, _processed, outbox = build_repositories(session)
    handler = PublishRecipeHandler(
        recipes, container.catalog_products, cache, container.entitlement_check, outbox
    )
    try:
        recipe = await handler.handle(
            PublishRecipeCommand(
                recipe_id=recipe_id, user_id=user_id, correlation_id=correlation_id
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return recipe_to_response(recipe)


@router.post(
    "/{recipe_id}/unpublish",
    response_model=RecipeResponse,
    summary="Remove a recipe from cross-user search (never a hard delete)",
)
async def unpublish_recipe(
    recipe_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
) -> RecipeResponse | JSONResponse:
    recipes, _cache, _processed, outbox = build_repositories(session)
    handler = UnpublishRecipeHandler(recipes, outbox)
    try:
        recipe = await handler.handle(
            UnpublishRecipeCommand(
                recipe_id=recipe_id, user_id=user_id, correlation_id=correlation_id
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return recipe_to_response(recipe)


@router.delete(
    "/{recipe_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    # No response body on success (a 204 must not have one); an error path
    # may still return a JSON error body via `map_exception`, so
    # `response_model` cannot be inferred from the return type annotation
    # (mirrors activity-service's `delete_exercise` precedent exactly).
    response_model=None,
    summary="Remove a recipe from cross-user search (soft-unpublish, never a hard row delete)",
)
async def delete_recipe(
    recipe_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
) -> Response | JSONResponse:
    recipes, _cache, _processed, outbox = build_repositories(session)
    handler = DeleteRecipeHandler(recipes, outbox)
    try:
        await handler.handle(
            DeleteRecipeCommand(recipe_id=recipe_id, user_id=user_id, correlation_id=correlation_id)
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
