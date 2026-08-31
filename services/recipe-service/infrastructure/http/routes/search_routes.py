"""`GET /api/v1/recipes/search?q=...` -- cross-user recipe search
(Pro-gated, implementation plan section 1.6). Kept in its own route
module (not `recipe_routes.py`) per implementation plan section 3's file
list -- this is the one route with genuinely different characteristics
(cross-user read, Pro-gated, never returns a draft)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from application.queries.search_published_recipes import (
    SearchPublishedRecipesHandler,
    SearchPublishedRecipesQuery,
)
from infrastructure.composition_root import Container, build_repositories
from infrastructure.http.dependencies import get_authenticated_user_id, get_container, get_session
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.recipe_schemas import RecipeListResponse, recipe_to_response

router = APIRouter(prefix="/api/v1/recipes", tags=["recipes"])


@router.get(
    "/search",
    response_model=RecipeListResponse,
    summary="Full-text search over published recipes (Pro-gated)",
    description="Entitlement is checked before any repository query is attempted. Never "
    "returns an unpublished/draft recipe, even the searching user's own.",
)
async def search_published_recipes(
    q: Annotated[str, Query(min_length=1)],
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[Container, Depends(get_container)],
) -> RecipeListResponse | JSONResponse:
    recipes, cache, _processed, _outbox = build_repositories(session)
    handler = SearchPublishedRecipesHandler(recipes, cache, container.entitlement_check)
    try:
        results = await handler.handle(SearchPublishedRecipesQuery(user_id=user_id, query_text=q))
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return RecipeListResponse(items=[recipe_to_response(r) for r in results])
