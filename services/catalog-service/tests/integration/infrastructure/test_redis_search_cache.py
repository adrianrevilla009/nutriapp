import pytest
from redis.asyncio import Redis

from domain.entities.product import Product
from domain.ports.search_read_port import ProductSearchPage, ProductSearchQuery
from infrastructure.caching.redis_search_cache import RedisSearchCache
from tests.fixtures.factories import make_raw_record


@pytest.fixture()
async def redis_client(redis_url):
    client = Redis.from_url(redis_url)
    yield client
    await client.flushall()
    await client.aclose()


async def _make_page() -> ProductSearchPage:
    product = Product.merge(existing=None, incoming=make_raw_record()).product
    return ProductSearchPage(items=(product,), total=1, page=1, page_size=20)


async def test_cache_miss_then_populate(redis_client):
    cache = RedisSearchCache(redis_client)
    query = ProductSearchQuery(
        text="chocolate", dietary_tags=frozenset(), allergen_tags_excluded=frozenset()
    )

    assert await cache.get(query) is None

    page = await _make_page()
    await cache.set(query, page)

    cached = await cache.get(query)
    assert cached is not None
    assert cached.total == 1
    assert cached.items[0].name == page.items[0].name


async def test_cache_hit_returns_same_data_as_set(redis_client):
    cache = RedisSearchCache(redis_client)
    query = ProductSearchQuery(
        text="bar", dietary_tags=frozenset(), allergen_tags_excluded=frozenset()
    )
    page = await _make_page()
    await cache.set(query, page)

    first = await cache.get(query)
    second = await cache.get(query)
    assert first.total == second.total == 1


async def test_product_update_invalidates_targeted_product_key(redis_client):
    cache = RedisSearchCache(redis_client)
    product = Product.merge(existing=None, incoming=make_raw_record()).product
    await cache.set_product(product)

    assert await cache.get_product(str(product.product_id)) is not None

    await cache.invalidate_product(str(product.product_id))

    assert await cache.get_product(str(product.product_id)) is None
