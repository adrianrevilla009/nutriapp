from __future__ import annotations

import uuid
from datetime import date

import pytest
from redis.asyncio import Redis

from domain.services.nutrient_total_calculator import calculate_entry_nutrient_total
from infrastructure.caching.redis_current_total_cache import RedisCurrentTotalCache

MACROS = {"calories_kcal": 200.0, "protein_g": 10.0, "carbs_g": 20.0, "fat_g": 5.0}


@pytest.fixture()
async def redis_client(redis_url):
    client = Redis.from_url(redis_url)
    yield client
    await client.flushall()
    await client.aclose()


async def test_cache_miss_then_hit(redis_client):
    cache = RedisCurrentTotalCache(redis_client)
    user_id = uuid.uuid4()
    total_date = date(2026, 8, 25)

    assert await cache.get(user_id, total_date) is None

    line = calculate_entry_nutrient_total(
        quantity_grams=150.0,
        macros_per_unit=MACROS,
        source_type="catalog_product",
        micronutrient_panel_per_100g={"sugars_g": 4.0},
    )
    await cache.set(user_id, total_date, line)

    cached = await cache.get(user_id, total_date)
    assert cached is not None
    assert cached.macros.calories_kcal == 300.0
    assert cached.micronutrients["sugars_g"] == 6.0


async def test_invalidate_removes_entry(redis_client):
    cache = RedisCurrentTotalCache(redis_client)
    user_id = uuid.uuid4()
    total_date = date(2026, 8, 25)
    line = calculate_entry_nutrient_total(
        quantity_grams=100.0,
        macros_per_unit=MACROS,
        source_type="ai_detected",
        micronutrient_panel_per_100g=None,
    )
    await cache.set(user_id, total_date, line)

    await cache.invalidate(user_id, total_date)

    assert await cache.get(user_id, total_date) is None


async def test_connection_failure_fails_open_on_get_set_and_invalidate():
    unreachable_client = Redis(host="127.0.0.1", port=1, socket_connect_timeout=1)
    cache = RedisCurrentTotalCache(unreachable_client)
    user_id = uuid.uuid4()
    total_date = date(2026, 8, 25)
    line = calculate_entry_nutrient_total(
        quantity_grams=100.0,
        macros_per_unit=MACROS,
        source_type="ai_detected",
        micronutrient_panel_per_100g=None,
    )

    assert await cache.get(user_id, total_date) is None
    await cache.set(user_id, total_date, line)  # must not raise
    await cache.invalidate(user_id, total_date)  # must not raise
    await unreachable_client.aclose()
