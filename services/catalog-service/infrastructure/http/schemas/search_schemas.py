"""Pydantic response schemas for GET /api/v1/catalog/products/search."""

from __future__ import annotations

from pydantic import BaseModel

from domain.ports.search_read_port import ProductSearchPage
from infrastructure.http.schemas.product_schemas import ProductResponse, product_to_response


class ProductSearchResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    page_size: int


def page_to_response(page: ProductSearchPage) -> ProductSearchResponse:
    return ProductSearchResponse(
        items=[product_to_response(p) for p in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )
