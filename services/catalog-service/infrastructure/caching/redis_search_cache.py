"""RedisSearchCache — implements SearchCachePort.

Cache-aside pattern (caching-strategy SKILL.md): `catalog:search-results:*`
15 min TTL. Product-level invalidation (`catalog:product:{id}`, 24h TTL)
is invalidated on `ProductUpdated` per that skill's example; best-effort
invalidation of any cached search-result page containing that product is
explicitly *not* attempted here (acceptable staleness within the 15 min
TTL — a deliberate simplification per the implementation plan section 7,
not a silent gap) — this adapter tracks the set of query-hashes it has
served so a full-namespace flush is possible, but does not attempt
per-product targeted invalidation of search pages.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from redis.asyncio import Redis

from domain.entities.product import Product
from domain.ports.search_read_port import ProductSearchPage, ProductSearchQuery
from domain.value_objects.allergen_tags import AllergenTag, AllergenTags
from domain.value_objects.barcode import Barcode
from domain.value_objects.dietary_tags import DietaryTag, DietaryTags
from domain.value_objects.nutrient_panel import NutrientPanel
from domain.value_objects.package_size import PackageSize, PackageUnit
from domain.value_objects.price import Price
from domain.value_objects.source_reference import SourceName

SEARCH_RESULTS_TTL_SECONDS = 15 * 60
PRODUCT_TTL_SECONDS = 24 * 60 * 60


def _query_hash(query: ProductSearchQuery) -> str:
    key_material = json.dumps(
        {
            "text": query.text,
            "dietary_tags": sorted(t.value for t in query.dietary_tags),
            "allergen_tags_excluded": sorted(t.value for t in query.allergen_tags_excluded),
            "page": query.page,
            "page_size": query.page_size,
        },
        sort_keys=True,
    )
    return hashlib.sha256(key_material.encode("utf-8")).hexdigest()


def _product_to_cache_dict(product: Product) -> dict[str, Any]:
    return {
        "product_id": str(product.product_id),
        "barcode": str(product.barcode) if product.barcode else None,
        "name": product.name,
        "brand": product.brand,
        "category": product.category,
        "nutrient_panel": product.nutrient_panel.as_dict() if product.nutrient_panel else None,
        "dietary_tags": [t.value for t in product.dietary_tags],
        "allergen_tags": [t.value for t in product.allergen_tags],
        "package_size": (
            {"value": product.package_size.value, "unit": product.package_size.unit.value}
            if product.package_size
            else None
        ),
        "price": (
            {"amount": product.price.amount, "currency": product.price.currency}
            if product.price
            else None
        ),
        "sources": sorted(s.value for s in product.sources),
        "catalogued_at": product.catalogued_at.isoformat(),
        "updated_at": product.updated_at.isoformat(),
    }


def _product_from_cache_dict(data: dict[str, Any]) -> Product:
    return Product(
        product_id=uuid.UUID(data["product_id"]),
        barcode=Barcode(data["barcode"]) if data.get("barcode") else None,
        name=data.get("name"),
        brand=data.get("brand"),
        category=data.get("category"),
        nutrient_panel=NutrientPanel(**data["nutrient_panel"])
        if data.get("nutrient_panel")
        else None,
        dietary_tags=DietaryTags(frozenset(DietaryTag(t) for t in data.get("dietary_tags", []))),
        allergen_tags=AllergenTags(
            frozenset(AllergenTag(t) for t in data.get("allergen_tags", []))
        ),
        package_size=(
            PackageSize(
                value=data["package_size"]["value"], unit=PackageUnit(data["package_size"]["unit"])
            )
            if data.get("package_size")
            else None
        ),
        price=(
            Price(amount=data["price"]["amount"], currency=data["price"]["currency"])
            if data.get("price")
            else None
        ),
        sources=frozenset(SourceName(s) for s in data.get("sources", [])),
        source_snapshots={},
        catalogued_at=datetime.fromisoformat(data["catalogued_at"]),
        updated_at=datetime.fromisoformat(data["updated_at"]),
    )


class RedisSearchCache:
    """Implements domain.ports.search_cache_port.SearchCachePort."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def _search_key(self, query: ProductSearchQuery) -> str:
        return f"catalog:search-results:{_query_hash(query)}"

    def _product_key(self, product_id: str) -> str:
        return f"catalog:product:{product_id}"

    async def get(self, query: ProductSearchQuery) -> ProductSearchPage | None:
        raw = await self._redis.get(self._search_key(query))
        if raw is None:
            return None
        data = json.loads(raw)
        items = tuple(_product_from_cache_dict(item) for item in data["items"])
        return ProductSearchPage(
            items=items, total=data["total"], page=data["page"], page_size=data["page_size"]
        )

    async def set(self, query: ProductSearchQuery, page: ProductSearchPage) -> None:
        data = {
            "items": [_product_to_cache_dict(p) for p in page.items],
            "total": page.total,
            "page": page.page,
            "page_size": page.page_size,
        }
        await self._redis.set(
            self._search_key(query), json.dumps(data), ex=SEARCH_RESULTS_TTL_SECONDS
        )

    async def invalidate_product(self, product_id: str) -> None:
        await self._redis.delete(self._product_key(product_id))

    async def get_product(self, product_id: str) -> Product | None:
        raw = await self._redis.get(self._product_key(product_id))
        if raw is None:
            return None
        return _product_from_cache_dict(json.loads(raw))

    async def set_product(self, product: Product) -> None:
        await self._redis.set(
            self._product_key(str(product.product_id)),
            json.dumps(_product_to_cache_dict(product)),
            ex=PRODUCT_TTL_SECONDS,
        )
