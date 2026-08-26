"""SearchCachePort — cache-aside wrapper around search reads
(caching-strategy SKILL.md: `catalog:search-results:*`, 15 min TTL)."""

from __future__ import annotations

from typing import Protocol

from domain.ports.search_read_port import ProductSearchPage, ProductSearchQuery


class SearchCachePort(Protocol):
    async def get(self, query: ProductSearchQuery) -> ProductSearchPage | None: ...

    async def set(self, query: ProductSearchQuery, page: ProductSearchPage) -> None: ...

    async def invalidate_product(self, product_id: str) -> None: ...
