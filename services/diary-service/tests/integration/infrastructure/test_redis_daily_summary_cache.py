from __future__ import annotations

import uuid
from datetime import date

import pytest
from redis.asyncio import Redis
from testcontainers.redis import RedisContainer

from infrastructure.cache.redis_daily_summary_cache import RedisDailySummaryCache

SUMMARY_DATE = date(2026, 8, 26)


@pytest.fixture(scope="module")
def redis_container():
    with RedisContainer("redis:7-alpine") as container:
        yield container


@pytest.fixture
async def redis_client(redis_container):
    client = Redis(
        host=redis_container.get_container_host_ip(),
        port=int(redis_container.get_exposed_port(6379)),
        decode_responses=True,
    )
    yield client
    await client.flushall()
    await client.aclose()


def _summary() -> dict:
    return dict(
        total_calories_kcal=500.0,
        total_protein_g=30.0,
        total_carbs_g=60.0,
        total_fat_g=10.0,
        total_water_ml=1000.0,
        fasting_windows_ended=1,
    )


async def test_cache_miss_then_set_populates_the_cache(redis_client):
    cache = RedisDailySummaryCache(redis_client)
    user_id = uuid.uuid4()

    assert await cache.get(user_id, SUMMARY_DATE) is None
    await cache.set(user_id, SUMMARY_DATE, _summary())
    cached = await cache.get(user_id, SUMMARY_DATE)
    assert cached["total_calories_kcal"] == 500.0


async def test_invalidate_removes_exactly_that_users_date_key_not_others(redis_client):
    cache = RedisDailySummaryCache(redis_client)
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    await cache.set(user_a, SUMMARY_DATE, _summary())
    await cache.set(user_b, SUMMARY_DATE, _summary())

    await cache.invalidate(user_a, SUMMARY_DATE)

    assert await cache.get(user_a, SUMMARY_DATE) is None
    assert await cache.get(user_b, SUMMARY_DATE) is not None


async def test_connection_failure_fails_open_returns_none_not_raise():
    unreachable_client = Redis(host="127.0.0.1", port=1, socket_connect_timeout=1)
    cache = RedisDailySummaryCache(unreachable_client)
    result = await cache.get(uuid.uuid4(), SUMMARY_DATE)
    assert result is None
    await unreachable_client.aclose()
