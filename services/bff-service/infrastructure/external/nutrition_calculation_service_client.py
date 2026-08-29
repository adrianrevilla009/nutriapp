"""NutritionCalculationServiceClient -- implements both NutritionTotalsPort
and NutritionTargetPort. Synchronous HTTP calls to nutrition-calculation-
service's two existing PUBLIC endpoints (`GET /api/v1/nutrition/totals/{date}`,
`GET /api/v1/nutrition/target` -- see
services/nutrition-calculation-service/infrastructure/http/routes/
nutrition_total_routes.py and target_routes.py), the exact same ones the
frontend would otherwise call directly through Kong (Open Host Service /
Customer-Supplier, implementation plan section 6).

The incoming request's `Authorization` header is forwarded UNCHANGED to
both calls.

Resilience (.claude/skills/resilience-patterns/SKILL.md, implementation
plan section 7): ONE class, ONE shared `httpx.AsyncClient` connection
pool (both calls hit the same host, so sharing a bulkhead here is the
correct pooling choice), but TWO INDEPENDENTLY NAMED `purgatory` circuit
breakers ("nutrition_totals", "nutrition_target") from the same breaker
factory -- purgatory tracks breaker state per name, so tripping one never
affects the other's health, per resilience-patterns/SKILL.md's "never
share one breaker across unrelated dependencies" (these two calls have
unrelated failure modes: the totals aggregation and the target
computation are independent read models). Each call also gets its own
`tenacity` retry (3 attempts, exponential backoff with jitter, transport
errors only) and the same tight timeout as the diary-service client (1s
connect / 3s read).

Known upstream gap (implementation plan section 1 acceptance criterion
3, services/nutrition-calculation-service/README.md): `get_target`'s
404 (`NUTRITION_TARGET_NOT_FOUND`) is a well-formed, EXPECTED business
response (a `Sex.OTHER` user, or a deferred recompute) -- it returns
`NutritionTargetNotComputedYet`, a plain value, NOT raised as an error,
and does NOT count toward the "nutrition_target" breaker's failure
threshold. Only a genuine service-health signal (a transport failure or
a 5xx response) counts toward either breaker.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import purgatory
from purgatory.domain.model import OpenedState
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from domain.ports.nutrition_target_port import (
    NutritionTargetNotComputedYet,
    NutritionTargetResult,
    NutritionTargetUnavailableError,
)
from domain.ports.nutrition_totals_port import (
    NutritionTotalsResult,
    NutritionTotalsUnavailableError,
)

TOTALS_CIRCUIT_NAME = "nutrition_totals"
TARGET_CIRCUIT_NAME = "nutrition_target"
DEFAULT_FAIL_MAX = 5
DEFAULT_RESET_TIMEOUT_SECONDS = 30


def _parse_totals(body: dict[str, Any]) -> NutritionTotalsResult:
    return NutritionTotalsResult(
        calories_kcal=body["calories_kcal"],
        protein_g=body["protein_g"],
        carbs_g=body["carbs_g"],
        fat_g=body["fat_g"],
        micronutrients=body.get("micronutrients"),
        micronutrients_status=body["micronutrients_status"],
        is_estimated=body["is_estimated"],
    )


def _parse_target(body: dict[str, Any]) -> NutritionTargetResult:
    return NutritionTargetResult(
        calorie_target_kcal=body["calorie_target_kcal"],
        protein_g_min=body["protein_g_min"],
        protein_g_max=body["protein_g_max"],
        fat_g_min=body["fat_g_min"],
        carbs_g=body["carbs_g"],
        goal_type=body["goal_type"],
    )


class NutritionCalculationServiceClient:
    """Implements domain.ports.nutrition_totals_port.NutritionTotalsPort
    and domain.ports.nutrition_target_port.NutritionTargetPort."""

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
        # ONE factory, TWO independently-tracked breaker names -- see
        # module docstring.
        self._breaker_factory = purgatory.AsyncCircuitBreakerFactory(
            default_threshold=fail_max, default_ttl=reset_timeout_seconds
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.2, max=2.0),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def _get_totals(self, total_date: date, authorization_header: str) -> httpx.Response:
        return await self._http.get(
            f"{self._base_url}/api/v1/nutrition/totals/{total_date.isoformat()}",
            headers={"Authorization": authorization_header},
        )

    async def get_totals(
        self, total_date: date, authorization_header: str
    ) -> NutritionTotalsResult:
        breaker = await self._breaker_factory.get_breaker(TOTALS_CIRCUIT_NAME)
        try:
            async with breaker:
                response = await self._get_totals(total_date, authorization_header)
                if response.status_code >= 500:
                    response.raise_for_status()
        except OpenedState as exc:
            raise NutritionTotalsUnavailableError(
                "nutrition-calculation-service totals circuit is open."
            ) from exc
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            raise NutritionTotalsUnavailableError(
                f"nutrition-calculation-service totals call failed: {exc}"
            ) from exc

        if response.status_code != 200:
            raise NutritionTotalsUnavailableError(
                f"nutrition-calculation-service totals call returned unexpected "
                f"status {response.status_code}."
            )

        try:
            return _parse_totals(response.json())
        except (KeyError, ValueError) as exc:
            raise NutritionTotalsUnavailableError(
                f"nutrition-calculation-service totals response was malformed: {exc}"
            ) from exc

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.2, max=2.0),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def _get_target(self, authorization_header: str) -> httpx.Response:
        return await self._http.get(
            f"{self._base_url}/api/v1/nutrition/target",
            headers={"Authorization": authorization_header},
        )

    async def get_target(
        self, authorization_header: str
    ) -> NutritionTargetResult | NutritionTargetNotComputedYet:
        breaker = await self._breaker_factory.get_breaker(TARGET_CIRCUIT_NAME)
        try:
            async with breaker:
                response = await self._get_target(authorization_header)
                if response.status_code >= 500:
                    response.raise_for_status()
        except OpenedState as exc:
            raise NutritionTargetUnavailableError(
                "nutrition-calculation-service target circuit is open."
            ) from exc
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            raise NutritionTargetUnavailableError(
                f"nutrition-calculation-service target call failed: {exc}"
            ) from exc

        # A well-formed 404 ("no target computed yet" -- Sex.OTHER/deferred
        # recompute, README.md's documented gap) is an EXPECTED business
        # response, never raised and never counted as a breaker failure
        # (it never enters the `async with breaker:` block above as an
        # exception).
        if response.status_code == 404:
            return NutritionTargetNotComputedYet()

        if response.status_code != 200:
            raise NutritionTargetUnavailableError(
                f"nutrition-calculation-service target call returned unexpected "
                f"status {response.status_code}."
            )

        try:
            return _parse_target(response.json())
        except (KeyError, ValueError) as exc:
            raise NutritionTargetUnavailableError(
                f"nutrition-calculation-service target response was malformed: {exc}"
            ) from exc

    async def aclose(self) -> None:
        await self._http.aclose()
