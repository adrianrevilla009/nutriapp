"""GetProductByIdQuery + handler."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from application.errors import ProductNotFoundError
from domain.entities.product import Product
from domain.ports.product_repository_port import ProductRepositoryPort


@dataclass(frozen=True, slots=True)
class GetProductByIdQuery:
    product_id: uuid.UUID


class GetProductByIdHandler:
    def __init__(self, product_repository: ProductRepositoryPort) -> None:
        self._products = product_repository

    async def handle(self, query: GetProductByIdQuery) -> Product:
        product = await self._products.get_by_id(query.product_id)
        if product is None:
            raise ProductNotFoundError(f"No product with id {query.product_id}.")
        return product
