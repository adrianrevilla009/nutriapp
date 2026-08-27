"""CatalogLookupClient -- implements CatalogLookupPort. Synchronous HTTP
call to catalog-service's internal barcode-lookup endpoint
(`/plans/catalog-service/implementation-plan.md` Addendum 2):
`GET /internal/v1/catalog/lookup?barcode={barcode}`, with the per-caller
service credential sent as a header. This client only ever SENDS the
credential; it has no knowledge of how catalog-service verifies it.

Response body reuses the same shape catalog-service's public
`GET /api/v1/catalog/products/{id}` already returns (Addendum 2's
explicit design decision, so no second schema is needed) -- parsed here
into this service's OWN `CatalogProduct` anticorruption-layer type
(CLAUDE.md section 2.5: never catalog-service's own `Product`/
`ProductResponse` types directly).

Resilience (`.claude/skills/resilience-patterns/SKILL.md`): a DEDICATED
`purgatory` circuit breaker (`fail_max=5`, `reset_timeout=30s`) -- never
shared with any other outbound client -- wraps a `tenacity` retry (3
attempts, exponential backoff with jitter, transient transport errors
only -- this call is idempotent, a read with no side effect) and an
explicit timeout (2s connect / 5s read). Own, isolated
`httpx.AsyncClient` connection pool (bulkhead).

Only a genuine service-health signal (a transport failure or a 5xx
response) counts toward the breaker's failure threshold -- a 404 ("no
matching product"), or 401/403 (bad credential) is a normal, well-formed
business response, not a health signal, and must not itself trip the
breaker.

On circuit-open or persistent failure, raises `CatalogLookupUnavailableError`
-- the caller (`DecodeBarcodeHandler`) must fall back to
`status="unavailable"` cleanly, never guess a product match.
"""

from __future__ import annotations

from typing import Any

import httpx
import purgatory
from purgatory.domain.model import OpenedState
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from domain.ports.catalog_lookup_port import CatalogLookupUnavailableError
from domain.value_objects.barcode import Barcode
from domain.value_objects.catalog_product import CatalogProduct, NutrientPanel, PackageSize

CIRCUIT_NAME = "catalog_lookup"
DEFAULT_FAIL_MAX = 5
DEFAULT_RESET_TIMEOUT_SECONDS = 30
CREDENTIAL_HEADER_NAME = "X-Internal-Service-Credential"


def _parse_product(body: dict[str, Any]) -> CatalogProduct:
    nutrition_raw = body.get("nutrition_per_100g")
    package_size_raw = body.get("package_size")
    return CatalogProduct(
        product_id=body["product_id"],
        barcode=body.get("barcode"),
        name=body.get("name"),
        brand=body.get("brand"),
        category=body.get("category"),
        nutrition_per_100g=(NutrientPanel(**nutrition_raw) if nutrition_raw else None),
        dietary_tags=list(body.get("dietary_tags", [])),
        allergen_tags=list(body.get("allergen_tags", [])),
        package_size=(PackageSize(**package_size_raw) if package_size_raw else None),
        sources=list(body.get("sources", [])),
    )


class CatalogLookupClient:
    """Implements domain.ports.catalog_lookup_port.CatalogLookupPort."""

    def __init__(
        self,
        base_url: str,
        credential: str,
        http_client: httpx.AsyncClient | None = None,
        fail_max: int = DEFAULT_FAIL_MAX,
        reset_timeout_seconds: int = DEFAULT_RESET_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._credential = credential
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
    async def _get(self, barcode: Barcode) -> httpx.Response:
        return await self._http.get(
            f"{self._base_url}/internal/v1/catalog/lookup",
            params={"barcode": str(barcode)},
            headers={CREDENTIAL_HEADER_NAME: self._credential},
        )

    async def lookup_by_barcode(self, barcode: Barcode) -> CatalogProduct | None:
        breaker = await self._breaker_factory.get_breaker(CIRCUIT_NAME)
        try:
            async with breaker:
                response = await self._get(barcode)
                if response.status_code >= 500:
                    response.raise_for_status()
        except OpenedState as exc:
            raise CatalogLookupUnavailableError(
                "catalog-service internal lookup circuit is open."
            ) from exc
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            raise CatalogLookupUnavailableError(
                f"catalog-service internal lookup call failed: {exc}"
            ) from exc

        if response.status_code == 404:
            return None
        if response.status_code in (401, 403):
            raise CatalogLookupUnavailableError(
                f"catalog-service rejected the lookup credential ({response.status_code})."
            )
        response.raise_for_status()

        return _parse_product(response.json())

    async def aclose(self) -> None:
        await self._http.aclose()
