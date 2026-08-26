import pytest

from application.errors import UnsupportedSearchFilterError
from application.queries.search_products import SearchProductsCommand, SearchProductsHandler
from domain.ports.search_read_port import ProductSearchPage, ProductSearchQuery
from tests.fixtures.factories import FakeSearchCache, FakeSearchReadModel


async def test_search_cache_miss_populates_cache_and_returns_page():
    page = ProductSearchPage(items=(), total=0, page=1, page_size=20)
    read_model = FakeSearchReadModel(page)
    cache = FakeSearchCache()
    handler = SearchProductsHandler(read_model, cache)

    result = await handler.handle(SearchProductsCommand(text="chocolate"))

    assert result is page
    assert read_model.calls == 1
    cached = await cache.get(
        ProductSearchQuery(
            text="chocolate",
            dietary_tags=frozenset(),
            allergen_tags_excluded=frozenset(),
            page=1,
            page_size=20,
        )
    )
    assert cached is page


async def test_search_cache_hit_skips_read_model():
    page = ProductSearchPage(items=(), total=0, page=1, page_size=20)
    read_model = FakeSearchReadModel(page)
    cache = FakeSearchCache()
    handler = SearchProductsHandler(read_model, cache)

    await handler.handle(SearchProductsCommand(text="chocolate"))
    await handler.handle(SearchProductsCommand(text="chocolate"))

    assert read_model.calls == 1


async def test_unsupported_dietary_filter_raises_application_error():
    read_model = FakeSearchReadModel()
    cache = FakeSearchCache()
    handler = SearchProductsHandler(read_model, cache)

    with pytest.raises(UnsupportedSearchFilterError):
        await handler.handle(SearchProductsCommand(text=None, dietary_tags=("not-a-real-tag",)))
