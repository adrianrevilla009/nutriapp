"""ProductCatalogued (v1) — see docs/events-catalog.md.

Renamed from the agent-doc's `ProductAdded` for PascalCase-past-tense
precision (implementation plan section 5): emitted the first time a
product (by dedup key) is written to `products`, regardless of which
source triggered it.
"""

from __future__ import annotations

from typing import Any

from domain.entities.product import Product
from domain.events.base import DomainEvent, EventMetadata

EVENT_TYPE = "ProductCatalogued"
EVENT_VERSION = 1


def build_product_payload(product: Product) -> dict[str, Any]:
    return {
        "product_id": str(product.product_id),
        "barcode": str(product.barcode) if product.barcode else None,
        "name": product.name,
        "brand": product.brand,
        "category": product.category,
        "nutrition_per_100g": product.nutrient_panel.as_dict() if product.nutrient_panel else None,
        "dietary_tags": [tag.value for tag in product.dietary_tags],
        "allergen_tags": [tag.value for tag in product.allergen_tags],
        "package_size": (
            {"value": product.package_size.value, "unit": product.package_size.unit.value}
            if product.package_size
            else None
        ),
        "sources": sorted(source.value for source in product.sources),
        "catalogued_at": product.catalogued_at.isoformat(),
    }


def build_product_catalogued_event(*, product: Product, correlation_id: str) -> DomainEvent:
    return DomainEvent(
        event_type=EVENT_TYPE,
        version=EVENT_VERSION,
        aggregate_id=str(product.product_id),
        payload=build_product_payload(product),
        metadata=EventMetadata(correlation_id=correlation_id),
    )
