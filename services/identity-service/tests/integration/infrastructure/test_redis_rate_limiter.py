import pytest
from redis.asyncio import Redis
from testcontainers.redis import RedisContainer

from domain.ports.rate_limiter_port import RateLimiterUnavailableError, RateLimitExceededError
from infrastructure.cache.redis_rate_limiter import RedisRateLimiter


@pytest.fixture(scope="module")
def redis_container():
    with RedisContainer("redis:7-alpine") as container:
        yield container


@pytest.fixture
async def redis_client(redis_container):
    client = Redis(
        host=redis_container.get_container_host_ip(),
        port=int(redis_container.get_exposed_port(6379)),
        decode_responses=False,
    )
    yield client
    await client.flushall()
    await client.aclose()


async def test_redis_rate_limiter__under_threshold__allows(redis_client):
    limiter = RedisRateLimiter(redis_client)
    for _ in range(3):
        await limiter.check_and_increment("k1", limit=5, window_seconds=60)


async def test_redis_rate_limiter__at_threshold__rejects(redis_client):
    limiter = RedisRateLimiter(redis_client)
    for _ in range(3):
        await limiter.check_and_increment("k2", limit=3, window_seconds=60)
    with pytest.raises(RateLimitExceededError):
        await limiter.check_and_increment("k2", limit=3, window_seconds=60)


async def test_redis_rate_limiter__resets_after_window(redis_client):
    limiter = RedisRateLimiter(redis_client)
    await limiter.check_and_increment("k3", limit=1, window_seconds=1)
    with pytest.raises(RateLimitExceededError):
        await limiter.check_and_increment("k3", limit=1, window_seconds=1)

    import asyncio

    await asyncio.sleep(1.2)
    await limiter.check_and_increment(
        "k3", limit=1, window_seconds=1
    )  # window reset, allowed again


async def test_redis_rate_limiter__connection_failure__fails_closed():
    unreachable_client = Redis(host="127.0.0.1", port=1, socket_connect_timeout=1)
    limiter = RedisRateLimiter(unreachable_client)
    with pytest.raises(RateLimiterUnavailableError):
        await limiter.check_and_increment("k4", limit=5, window_seconds=60)
    await unreachable_client.aclose()
