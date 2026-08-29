"""DiaryServiceClient -- implements DiarySummaryPort. Synchronous HTTP
call to diary-service's existing PUBLIC endpoint
(`GET /api/v1/diary/summary?date={date}`, the exact same one the
frontend would otherwise call directly through Kong -- see
services/diary-service/infrastructure/http/routes/daily_summary_routes.py),
called server-to-server here purely to do the fan-out/composition the
frontend would otherwise have to do itself (implementation plan section
6 -- Open Host Service / Customer-Supplier, NOT the internal-reveal-
endpoint exception pattern used elsewhere in this system).

The incoming request's `Authorization` header is forwarded UNCHANGED
(implementation plan section 1 acceptance criterion 1) -- diary-service
already validates the JWT signature itself; this client never re-derives
or re-signs anything.

Resilience (.claude/skills/resilience-patterns/SKILL.md): a DEDICATED
`purgatory` circuit breaker (name "diary_summary", fail_max=5,
reset_timeout=30s) wraps a `tenacity` retry (3 attempts, exponential
backoff with jitter, transport errors only -- this call is a read, safe
to retry unconditionally) and an explicit timeout (1s connect / 3s read,
tighter than a typical write-path call since this is a synchronous,
user-waiting dashboard load, per implementation plan section 7). Own,
isolated `httpx.AsyncClient` connection pool (bulkhead), never shared
with the nutrition-calculation-service client.

Only a genuine service-health signal (a transport failure or a 5xx
response) counts toward the breaker's failure threshold.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import purgatory
from purgatory.domain.model import OpenedState
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from domain.ports.diary_summary_port import DiarySummaryResult, DiarySummaryUnavailableError

CIRCUIT_NAME = "diary_summary"
DEFAULT_FAIL_MAX = 5
DEFAULT_RESET_TIMEOUT_SECONDS = 30


def _parse_summary(body: dict[str, Any]) -> DiarySummaryResult:
    return DiarySummaryResult(
        total_calories_kcal=body["total_calories_kcal"],
        total_protein_g=body["total_protein_g"],
        total_carbs_g=body["total_carbs_g"],
        total_fat_g=body["total_fat_g"],
        total_water_ml=body["total_water_ml"],
        fasting_windows_ended=body["fasting_windows_ended"],
    )


class DiaryServiceClient:
    """Implements domain.ports.diary_summary_port.DiarySummaryPort."""

    def __init__(
        self,
        base_url: str,
        http_client: httpx.AsyncClient | None = None,
        fail_max: int = DEFAULT_FAIL_MAX,
        reset_timeout_seconds: float = DEFAULT_RESET_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(connect=1.0, read=3.0, write=1.0, pool=1.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
        self._breaker_factory = purgatory.AsyncCircuitBreakerFactory(
            default_threshold=fail_max, default_ttl=reset_timeout_seconds
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.2, max=2.0),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def _get(self, summary_date: date, authorization_header: str) -> httpx.Response:
        return await self._http.get(
            f"{self._base_url}/api/v1/diary/summary",
            params={"date": summary_date.isoformat()},
            headers={"Authorization": authorization_header},
        )

    async def get_summary(
        self, summary_date: date, authorization_header: str
    ) -> DiarySummaryResult:
        breaker = await self._breaker_factory.get_breaker(CIRCUIT_NAME)
        try:
            async with breaker:
                response = await self._get(summary_date, authorization_header)
                if response.status_code >= 500:
                    response.raise_for_status()
        except OpenedState as exc:
            raise DiarySummaryUnavailableError("diary-service summary circuit is open.") from exc
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            raise DiarySummaryUnavailableError(f"diary-service summary call failed: {exc}") from exc

        if response.status_code != 200:
            raise DiarySummaryUnavailableError(
                f"diary-service summary call returned unexpected status {response.status_code}."
            )

        try:
            return _parse_summary(response.json())
        except (KeyError, ValueError) as exc:
            raise DiarySummaryUnavailableError(
                f"diary-service summary response was malformed: {exc}"
            ) from exc

    async def aclose(self) -> None:
        await self._http.aclose()
