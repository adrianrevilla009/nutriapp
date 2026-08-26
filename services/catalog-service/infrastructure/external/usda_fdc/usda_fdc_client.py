"""UsdaFdcClient — httpx client, own connection pool (bulkhead), per
implementation plan section 7:
- Explicit timeout: 10s connect / 30s read.
- `tenacity` retry: exponential backoff with jitter, max 3 attempts, only
  for transient transport errors (safe because USDA's Branded Foods
  lookup-by-page is idempotent, no side effect on the USDA side).
- A proactive token-bucket rate limiter (Redis-backed counter,
  `catalog:usda-rate-limit:{hour_bucket}`) — respects USDA's published
  1000 requests/hour/IP limit rather than relying on retry-after-429
  alone, per external-data-ethics SKILL.md.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

import httpx
from redis.asyncio import Redis
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

DEFAULT_BASE_URL = "https://api.nal.usda.gov/fdc/v1"
DEFAULT_RATE_LIMIT_PER_HOUR = 1000


class UsdaFdcRateLimitedError(Exception):
    """Raised on a proactive rate-limit throttle or a live 429 response —
    caught by `UsdaFdcSourceAdapter`, never propagated as a hard ingestion
    failure (test-plan section 2)."""


def _hour_bucket() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H")


class UsdaFdcClient:
    def __init__(
        self,
        redis: Redis,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        http_client: httpx.AsyncClient | None = None,
        rate_limit_per_hour: int = DEFAULT_RATE_LIMIT_PER_HOUR,
    ) -> None:
        self._redis = redis
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._rate_limit_per_hour = rate_limit_per_hour
        # Own, isolated connection pool (bulkhead) — never shared with any
        # other outbound client this service may add later.
        self._http = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

    async def _check_rate_limit(self) -> None:
        key = f"catalog:usda-rate-limit:{_hour_bucket()}"
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, 3600)
        if count > self._rate_limit_per_hour:
            raise UsdaFdcRateLimitedError(
                f"USDA FDC hourly rate limit ({self._rate_limit_per_hour}) exceeded."
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def _get(self, path: str, params: dict[str, Any]) -> httpx.Response:
        return await self._http.get(f"{self._base_url}{path}", params=params)

    async def fetch_branded_foods_page(
        self, page_number: int, page_size: int = 200
    ) -> dict[str, Any]:
        await self._check_rate_limit()
        response = await self._get(
            "/foods/search",
            {
                "api_key": self._api_key,
                "dataType": "Branded",
                "pageNumber": page_number,
                "pageSize": page_size,
            },
        )
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise UsdaFdcRateLimitedError(f"USDA FDC responded 429 (Retry-After={retry_after}).")
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    async def aclose(self) -> None:
        await self._http.aclose()
