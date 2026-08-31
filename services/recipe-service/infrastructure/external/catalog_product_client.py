"""CatalogProductClient -- implements CatalogProductPort. Calls
catalog-service's existing PUBLIC `GET /api/v1/catalog/products/{id}`
endpoint (implementation plan section 1/architecture-agent's confirmed
design) -- no internal credential header, since this is the same public,
unauthenticated route the frontend itself calls (per catalog-service's
own `product_routes.py`).

Own, DEDICATED `purgatory` circuit breaker (`catalog_product_lookup`) --
never shared with `billing_entitlement_check` (implementation plan
section 7: "Two independently-named circuit breakers ... must not share
breaker state") -- wrapping a `tenacity` retry (transient transport
errors only, this is an idempotent read) and an explicit timeout. Own,
isolated `httpx.AsyncClient` connection pool (bulkhead).

Only a genuine service-health signal (a transport failure or a 5xx
response) counts toward the breaker's failure threshold -- a 404
("no such product") is a normal, well-formed business response, not a
health signal, and must not itself trip the breaker (mirrors
food-recognition-service's `CatalogLookupClient` precedent exactly).
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import purgatory
from purgatory.domain.model import OpenedState
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from domain.ports.catalog_product_port import (
    CatalogProductUnavailableError,
    ResolvedIngredientProduct,
)
from domain.value_objects.nutrient_panel import NutrientPanel

CIRCUIT_NAME = "catalog_product_lookup"
DEFAULT_FAIL_MAX = 5
DEFAULT_RESET_TIMEOUT_SECONDS = 30


def _parse_panel(raw: dict[str, Any] | None) -> NutrientPanel | None:
    if raw is None:
        return None
    return NutrientPanel(
        energy_kcal=raw.get("energy_kcal"),
        protein_g=raw.get("protein_g"),
        carbohydrates_g=raw.get("carbohydrates_g"),
        fat_g=raw.get("fat_g"),
        sugars_g=raw.get("sugars_g"),
        fiber_g=raw.get("fiber_g"),
        saturated_fat_g=raw.get("saturated_fat_g"),
        sodium_mg=raw.get("sodium_mg"),
        salt_g=raw.get("salt_g"),
        calcium_mg=raw.get("calcium_mg"),
        iron_mg=raw.get("iron_mg"),
        vitamin_c_mg=raw.get("vitamin_c_mg"),
    )


class CatalogProductClient:
    """Implements domain.ports.catalog_product_port.CatalogProductPort."""

    def __init__(
        self,
        base_url: str,
        http_client: httpx.AsyncClient | None = None,
        fail_max: int = DEFAULT_FAIL_MAX,
        reset_timeout_seconds: float = DEFAULT_RESET_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(connect=2.0, read=5.0, write=2.0, pool=2.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
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
    async def _get(self, product_id: uuid.UUID) -> httpx.Response:
        return await self._http.get(f"{self._base_url}/api/v1/catalog/products/{product_id}")

    async def get_product(self, product_id: uuid.UUID) -> ResolvedIngredientProduct | None:
        breaker = await self._breaker_factory.get_breaker(CIRCUIT_NAME)
        try:
            async with breaker:
                response = await self._get(product_id)
                if response.status_code >= 500:
                    response.raise_for_status()
        except OpenedState as exc:
            raise CatalogProductUnavailableError(
                "catalog-service product lookup circuit is open."
            ) from exc
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            raise CatalogProductUnavailableError(
                f"catalog-service product lookup call failed: {exc}"
            ) from exc

        if response.status_code == 404:
            return None
        response.raise_for_status()

        body = response.json()
        return ResolvedIngredientProduct(
            product_id=uuid.UUID(str(body["product_id"])),
            nutrition_per_100g=_parse_panel(body.get("nutrition_per_100g")),
        )

    async def aclose(self) -> None:
        await self._http.aclose()
