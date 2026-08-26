"""GET /api/v1/catalog/products/{id} route."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from application.queries.get_product_by_id import GetProductByIdHandler, GetProductByIdQuery
from infrastructure.composition_root import build_repositories
from infrastructure.http.dependencies import get_session
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.product_schemas import ProductResponse, product_to_response

router = APIRouter(prefix="/api/v1/catalog", tags=["products"])


@router.get(
    "/products/{product_id}",
    response_model=ProductResponse,
    summary="Get a single catalogued product by id",
)
async def get_product(
    product_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ProductResponse | JSONResponse:
    products_repo, _outbox_repo, _search_read = build_repositories(session)
    handler = GetProductByIdHandler(products_repo)
    try:
        product = await handler.handle(GetProductByIdQuery(product_id=product_id))
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return product_to_response(product)
