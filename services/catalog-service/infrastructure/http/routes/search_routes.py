"""GET /api/v1/catalog/products/search route. Thin controller only —
parse query params into a command DTO, call the application handler,
serialize the result (api-conventions SKILL.md)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from application.queries.search_products import SearchProductsCommand, SearchProductsHandler
from infrastructure.composition_root import Container, build_repositories
from infrastructure.http.dependencies import get_container, get_session
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.search_schemas import ProductSearchResponse, page_to_response

router = APIRouter(prefix="/api/v1/catalog", tags=["search"])


@router.get(
    "/products/search",
    response_model=ProductSearchResponse,
    summary="Full-text/faceted product search",
    description="Postgres tsvector/GIN + pg_trgm search (ADR-0012) with dietary/allergen filters.",
)
async def search_products(
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[Container, Depends(get_container)],
    q: Annotated[str | None, Query(description="Free-text search query")] = None,
    dietary_tags: Annotated[list[str], Query()] = [],  # noqa: B006 -- FastAPI reads this once at route setup, never mutated per-request
    exclude_allergens: Annotated[list[str], Query()] = [],  # noqa: B006
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ProductSearchResponse | JSONResponse:
    _products_repo, _outbox_repo, search_read = build_repositories(session)
    handler = SearchProductsHandler(search_read, container.search_cache)
    try:
        page_result = await handler.handle(
            SearchProductsCommand(
                text=q,
                dietary_tags=tuple(dietary_tags),
                allergen_tags_excluded=tuple(exclude_allergens),
                page=page,
                page_size=page_size,
            )
        )
    except Exception as exc:  # noqa: BLE001 — mapped centrally below
        return map_exception(exc)
    return page_to_response(page_result)
