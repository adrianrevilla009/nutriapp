"""SearchProductsQuery + handler — cache-aside over SearchReadPort
(caching-strategy SKILL.md: `catalog:search-results:*`, 15 min TTL)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

from application.errors import UnsupportedSearchFilterError
from domain.ports.search_cache_port import SearchCachePort
from domain.ports.search_read_port import (
    ProductSearchPage,
    ProductSearchQuery,
    SearchReadPort,
)
from domain.value_objects.allergen_tags import AllergenTag
from domain.value_objects.dietary_tags import DietaryTag


@dataclass(frozen=True, slots=True)
class SearchProductsCommand:
    text: str | None
    dietary_tags: tuple[str, ...] = ()
    allergen_tags_excluded: tuple[str, ...] = ()
    page: int = 1
    page_size: int = 20


TagEnumT = TypeVar("TagEnumT", bound=Enum)


def _parse_tags(raw_values: tuple[str, ...], enum_cls: type[TagEnumT]) -> frozenset[TagEnumT]:
    parsed: set[TagEnumT] = set()
    for raw in raw_values:
        try:
            parsed.add(enum_cls(raw))
        except ValueError as exc:
            raise UnsupportedSearchFilterError(
                f"Unsupported filter value {raw!r} for {enum_cls.__name__}."
            ) from exc
    return frozenset(parsed)


class SearchProductsHandler:
    def __init__(self, search_read: SearchReadPort, search_cache: SearchCachePort) -> None:
        self._search_read = search_read
        self._search_cache = search_cache

    async def handle(self, command: SearchProductsCommand) -> ProductSearchPage:
        query = ProductSearchQuery(
            text=command.text,
            dietary_tags=_parse_tags(command.dietary_tags, DietaryTag),
            allergen_tags_excluded=_parse_tags(command.allergen_tags_excluded, AllergenTag),
            page=command.page,
            page_size=command.page_size,
        )

        cached = await self._search_cache.get(query)
        if cached is not None:
            return cached

        page = await self._search_read.search(query)
        await self._search_cache.set(query, page)
        return page
