"""SearchReadPort — search-facing read port (query object -> Product page).
Backed by Postgres tsvector/GIN + pg_trgm per ADR-0012."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from domain.entities.product import Product
from domain.value_objects.allergen_tags import AllergenTag
from domain.value_objects.dietary_tags import DietaryTag


@dataclass(frozen=True, slots=True)
class ProductSearchQuery:
    text: str | None
    dietary_tags: frozenset[DietaryTag]
    allergen_tags_excluded: frozenset[AllergenTag]
    page: int = 1
    page_size: int = 20


@dataclass(frozen=True, slots=True)
class ProductSearchPage:
    items: tuple[Product, ...]
    total: int
    page: int
    page_size: int


class SearchReadPort(Protocol):
    async def search(self, query: ProductSearchQuery) -> ProductSearchPage: ...
