"""ProductRepositoryPort — write-model persistence boundary."""

from __future__ import annotations

import uuid
from typing import Protocol

from domain.entities.product import Product
from domain.value_objects.barcode import Barcode


class ProductRepositoryPort(Protocol):
    async def get_by_id(self, product_id: uuid.UUID) -> Product | None: ...

    async def get_by_barcode(self, barcode: Barcode) -> Product | None: ...

    async def get_by_source_reference(
        self, source: str, source_product_id: str
    ) -> Product | None: ...

    async def save(self, product: Product) -> None: ...
