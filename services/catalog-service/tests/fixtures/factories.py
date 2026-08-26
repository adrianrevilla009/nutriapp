"""Shared test fixtures/factories — RawProductRecord builders and in-memory
fake port implementations (hexagonal-architecture SKILL.md: "Application:
unit tests using fake/in-memory implementations of ports, not the real
adapters")."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from application.dto.raw_product_record import RawProductRecord
from domain.entities.product import Product
from domain.events.base import DomainEvent
from domain.ports.search_read_port import ProductSearchPage, ProductSearchQuery
from domain.value_objects.allergen_tags import AllergenTags
from domain.value_objects.barcode import Barcode
from domain.value_objects.dietary_tags import DietaryTags
from domain.value_objects.nutrient_panel import NutrientPanel
from domain.value_objects.source_reference import SourceName

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_raw_record(**overrides) -> RawProductRecord:
    defaults = dict(
        source=SourceName.OPEN_FOOD_FACTS,
        source_product_id="off-1",
        barcode=Barcode("5901234123457"),
        name="Chocolate Bar",
        brand="Acme",
        category="Snacks",
        nutrient_panel=NutrientPanel(energy_kcal=500, protein_g=5, carbohydrates_g=50, fat_g=20),
        dietary_tags=DietaryTags.empty(),
        allergen_tags=AllergenTags.empty(),
        package_size=None,
        price=None,
        observed_at=NOW,
    )
    defaults.update(overrides)
    return RawProductRecord(**defaults)


class FakeProductRepository:
    def __init__(self) -> None:
        self.by_id: dict[uuid.UUID, Product] = {}

    async def get_by_id(self, product_id: uuid.UUID) -> Product | None:
        return self.by_id.get(product_id)

    async def get_by_barcode(self, barcode: Barcode) -> Product | None:
        for product in self.by_id.values():
            if product.barcode == barcode:
                return product
        return None

    async def get_by_source_reference(self, source: str, source_product_id: str) -> Product | None:
        for product in self.by_id.values():
            for src, snapshot in product.source_snapshots.items():
                if src.value == source and snapshot.source_product_id == source_product_id:
                    return product
        return None

    async def save(self, product: Product) -> None:
        self.by_id[product.product_id] = product


class FakeOutboxRepository:
    def __init__(self) -> None:
        self.enqueued: list[DomainEvent] = []
        self.published_ids: set[uuid.UUID] = set()

    async def enqueue(self, event: DomainEvent) -> None:
        self.enqueued.append(event)

    async def fetch_unpublished(self, limit: int = 100) -> list[DomainEvent]:
        return [e for e in self.enqueued if e.event_id not in self.published_ids][:limit]

    async def mark_published(self, event_id: uuid.UUID) -> None:
        self.published_ids.add(event_id)


class FakeSearchReadModel:
    def __init__(self, page: ProductSearchPage | None = None) -> None:
        self.page = page or ProductSearchPage(items=(), total=0, page=1, page_size=20)
        self.calls = 0

    async def search(self, query: ProductSearchQuery) -> ProductSearchPage:
        self.calls += 1
        return self.page


class FakeSearchCache:
    def __init__(self) -> None:
        self._store: dict[tuple, ProductSearchPage] = {}
        self.invalidated: list[str] = []

    def _key(self, query: ProductSearchQuery):
        return (
            query.text,
            query.dietary_tags,
            query.allergen_tags_excluded,
            query.page,
            query.page_size,
        )

    async def get(self, query: ProductSearchQuery) -> ProductSearchPage | None:
        return self._store.get(self._key(query))

    async def set(self, query: ProductSearchQuery, page: ProductSearchPage) -> None:
        self._store[self._key(query)] = page

    async def invalidate_product(self, product_id: str) -> None:
        self.invalidated.append(product_id)


class FakeCatalogSource:
    def __init__(self, batches) -> None:
        self._batches = list(batches)
        self._index = 0

    async def fetch_batch(self, cursor):
        batch = self._batches[self._index]
        self._index += 1
        return batch
