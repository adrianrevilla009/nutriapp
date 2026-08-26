"""Shared JSON (de)serialization helpers between domain value objects and
JSONB columns — used by both PostgresProductRepository and
PostgresSearchReadModel so the wire shape stays in one place."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from application.dto.raw_product_record import RawProductRecord
from domain.entities.product import Product
from domain.value_objects.allergen_tags import AllergenTag, AllergenTags
from domain.value_objects.barcode import Barcode
from domain.value_objects.dietary_tags import DietaryTag, DietaryTags
from domain.value_objects.nutrient_panel import NutrientPanel
from domain.value_objects.package_size import PackageSize, PackageUnit
from domain.value_objects.price import Price
from domain.value_objects.source_reference import SourceName
from infrastructure.persistence.models import ProductModel


def nutrient_panel_to_json(panel: NutrientPanel | None) -> dict[str, Any] | None:
    return panel.as_dict() if panel is not None else None


def nutrient_panel_from_json(data: dict[str, Any] | None) -> NutrientPanel | None:
    if not data:
        return None
    return NutrientPanel(**data)


def package_size_to_json(size: PackageSize | None) -> dict[str, Any] | None:
    if size is None:
        return None
    return {"value": size.value, "unit": size.unit.value}


def package_size_from_json(data: dict[str, Any] | None) -> PackageSize | None:
    if not data:
        return None
    return PackageSize(value=data["value"], unit=PackageUnit(data["unit"]))


def price_to_json(price: Price | None) -> dict[str, Any] | None:
    if price is None:
        return None
    return {"amount": price.amount, "currency": price.currency}


def price_from_json(data: dict[str, Any] | None) -> Price | None:
    if not data:
        return None
    return Price(amount=data["amount"], currency=data["currency"])


def raw_record_to_json(record: RawProductRecord) -> dict[str, Any]:
    return {
        "source": record.source.value,
        "source_product_id": record.source_product_id,
        "barcode": str(record.barcode) if record.barcode else None,
        "name": record.name,
        "brand": record.brand,
        "category": record.category,
        "nutrient_panel": nutrient_panel_to_json(record.nutrient_panel),
        "dietary_tags": [t.value for t in record.dietary_tags],
        "allergen_tags": [t.value for t in record.allergen_tags],
        "package_size": package_size_to_json(record.package_size),
        "price": price_to_json(record.price),
        "observed_at": record.observed_at.isoformat(),
    }


def raw_record_from_json(data: dict[str, Any]) -> RawProductRecord:
    return RawProductRecord(
        source=SourceName(data["source"]),
        source_product_id=data["source_product_id"],
        barcode=Barcode(data["barcode"]) if data.get("barcode") else None,
        name=data.get("name"),
        brand=data.get("brand"),
        category=data.get("category"),
        nutrient_panel=nutrient_panel_from_json(data.get("nutrient_panel")),
        dietary_tags=DietaryTags(frozenset(DietaryTag(t) for t in data.get("dietary_tags", []))),
        allergen_tags=AllergenTags(
            frozenset(AllergenTag(t) for t in data.get("allergen_tags", []))
        ),
        package_size=package_size_from_json(data.get("package_size")),
        price=price_from_json(data.get("price")),
        observed_at=datetime.fromisoformat(data["observed_at"]),
    )


def model_to_product_without_sources(model: ProductModel) -> Product:
    """Builds a `Product` from a `ProductModel` row without a per-row
    `product_sources` lookup — used by the search read model, where
    per-source provenance detail isn't part of the search response shape
    and an extra query per result row would be wasteful. A deliberate
    simplification, not an oversight: `PostgresProductRepository` is the
    path that returns the full `source_snapshots` mapping."""
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
        source_snapshots={},
        catalogued_at=model.catalogued_at,
        updated_at=model.updated_at,
    )
