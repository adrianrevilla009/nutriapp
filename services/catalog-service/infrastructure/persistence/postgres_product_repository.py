"""PostgresProductRepository — implements ProductRepositoryPort.

`save()` upserts both the `products` row and every source's
`product_sources` row inside the same session/transaction the caller
controls (application handlers own the commit boundary, same convention
as identity-service).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.product import Product
from domain.value_objects.allergen_tags import AllergenTag, AllergenTags
from domain.value_objects.barcode import Barcode
from domain.value_objects.dietary_tags import DietaryTag, DietaryTags
from domain.value_objects.source_reference import SourceName
from infrastructure.persistence.mappers import (
    nutrient_panel_from_json,
    nutrient_panel_to_json,
    package_size_from_json,
    package_size_to_json,
    price_from_json,
    price_to_json,
    raw_record_from_json,
    raw_record_to_json,
)
from infrastructure.persistence.models import ProductModel, ProductSourceModel


class PostgresProductRepository:
    """Implements domain.ports.product_repository_port.ProductRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, product_id: uuid.UUID) -> Product | None:
        model = await self._session.get(ProductModel, product_id)
        if model is None:
            return None
        return await self._to_domain(model)

    async def get_by_barcode(self, barcode: Barcode) -> Product | None:
        stmt = select(ProductModel).where(ProductModel.barcode == str(barcode))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return await self._to_domain(model)

    async def get_by_source_reference(self, source: str, source_product_id: str) -> Product | None:
        stmt = select(ProductSourceModel).where(
            ProductSourceModel.source == source,
            ProductSourceModel.source_product_id == source_product_id,
        )
        result = await self._session.execute(stmt)
        source_row = result.scalar_one_or_none()
        if source_row is None:
            return None
        return await self.get_by_id(source_row.product_id)

    async def _to_domain(self, model: ProductModel) -> Product:
        source_rows_stmt = select(ProductSourceModel).where(
            ProductSourceModel.product_id == model.product_id
        )
        result = await self._session.execute(source_rows_stmt)
        source_snapshots = {
            SourceName(row.source): raw_record_from_json(row.raw_snapshot)
            for row in result.scalars()
        }
        return Product(
            product_id=model.product_id,
            barcode=Barcode(model.barcode) if model.barcode else None,
            name=model.name,
            brand=model.brand,
            category=model.category,
            nutrient_panel=nutrient_panel_from_json(model.nutrient_panel),
            dietary_tags=DietaryTags(frozenset(DietaryTag(t) for t in model.dietary_tags)),
            allergen_tags=AllergenTags(frozenset(AllergenTag(t) for t in model.allergen_tags)),
            package_size=package_size_from_json(model.package_size),
            price=price_from_json(model.price),
            sources=frozenset(SourceName(s) for s in model.sources),
            source_snapshots=source_snapshots,
            catalogued_at=model.catalogued_at,
            updated_at=model.updated_at,
        )

    async def save(self, product: Product) -> None:
        model = await self._session.get(ProductModel, product.product_id)
        if model is None:
            model = ProductModel(product_id=product.product_id)
            self._session.add(model)

        model.barcode = str(product.barcode) if product.barcode else None
        model.name = product.name
        model.brand = product.brand
        model.category = product.category
        model.nutrient_panel = nutrient_panel_to_json(product.nutrient_panel)
        model.dietary_tags = [t.value for t in product.dietary_tags]
        model.allergen_tags = [t.value for t in product.allergen_tags]
        model.package_size = package_size_to_json(product.package_size)
        model.price = price_to_json(product.price)
        model.sources = sorted(s.value for s in product.sources)
        model.catalogued_at = product.catalogued_at
        model.updated_at = product.updated_at

        for source, record in product.source_snapshots.items():
            stmt = select(ProductSourceModel).where(
                ProductSourceModel.source == source.value,
                ProductSourceModel.source_product_id == record.source_product_id,
            )
            result = await self._session.execute(stmt)
            source_row = result.scalar_one_or_none()
            if source_row is None:
                source_row = ProductSourceModel(
                    id=uuid.uuid4(),
                    product_id=product.product_id,
                    source=source.value,
                    source_product_id=record.source_product_id,
                )
                self._session.add(source_row)
            source_row.product_id = product.product_id
            source_row.raw_snapshot = raw_record_to_json(record)
            source_row.observed_at = record.observed_at

        await self._session.flush()
