"""GetProductByBarcodeQuery + handler.

Thin wrapper over `ProductRepositoryPort.get_by_barcode()` (already
implemented and exercised today only by `product_deduplicator` during
ingestion) — this is that method's first read-path consumer, backing the
internal `GET /internal/v1/catalog/lookup` route (implementation plan
Addendum 2). Mirrors `GetProductByIdHandler`'s shape exactly, including
raising the same `ProductNotFoundError` on a miss.
"""

from __future__ import annotations

from dataclasses import dataclass

from application.errors import ProductNotFoundError
from domain.entities.product import Product
from domain.ports.product_repository_port import ProductRepositoryPort
from domain.value_objects.barcode import Barcode


@dataclass(frozen=True, slots=True)
class GetProductByBarcodeQuery:
    barcode: Barcode


class GetProductByBarcodeHandler:
    def __init__(self, product_repository: ProductRepositoryPort) -> None:
        self._products = product_repository

    async def handle(self, query: GetProductByBarcodeQuery) -> Product:
        product = await self._products.get_by_barcode(query.barcode)
        if product is None:
            raise ProductNotFoundError(f"No product with barcode {query.barcode}.")
        return product
