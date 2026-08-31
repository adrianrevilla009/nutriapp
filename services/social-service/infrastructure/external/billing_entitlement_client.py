"""BillingEntitlementClient -- implements EntitlementCheckPort. Calls
billing-service's internal, non-Kong-routed
`GET /internal/v1/billing/entitlements/{user_id}` (implementation plan
section 1.2/3), sending the shared `X-Internal-Service-Credential` this
service is provisioned with (same single-shared-credential mechanism as
recipe-service's/identity-service's/catalog-service's other
internal-endpoint consumers).

Own, DEDICATED `purgatory` circuit breaker (`billing_entitlement_check`),
mirroring `recipe-service`'s adapter of the same name verbatim (this
codebase's now-standard entitlement-check client pattern). Used ONLY on
an `EntitlementCacheRepositoryPort` cache miss -- the caller
(`application/entitlement_check.py`'s `is_user_entitled`) decides that,
not this adapter.

Only a genuine service-health signal (a transport failure or a 5xx
response) counts toward the breaker's failure threshold -- an invalid/
missing credential (401/403) is a normal, well-formed rejection, not a
health signal, but IS still surfaced as `EntitlementCheckUnavailableError`
(a misconfigured credential must fail safe -- not entitled -- same as any
other unavailability, never silently retried as if it might succeed)."""

from __future__ import annotations

import uuid

import httpx
import purgatory
from purgatory.domain.model import OpenedState
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from domain.ports.entitlement_check_port import EntitlementCheckUnavailableError

CIRCUIT_NAME = "billing_entitlement_check"
DEFAULT_FAIL_MAX = 5
DEFAULT_RESET_TIMEOUT_SECONDS = 30
CREDENTIAL_HEADER_NAME = "X-Internal-Service-Credential"


class BillingEntitlementClient:
    """Implements domain.ports.entitlement_check_port.EntitlementCheckPort."""

    def __init__(
        self,
        base_url: str,
        credential: str,
        http_client: httpx.AsyncClient | None = None,
        fail_max: int = DEFAULT_FAIL_MAX,
        reset_timeout_seconds: float = DEFAULT_RESET_TIMEOUT_SECONDS,
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
    async def _get(self, user_id: uuid.UUID) -> httpx.Response:
        return await self._http.get(
            f"{self._base_url}/internal/v1/billing/entitlements/{user_id}",
            headers={CREDENTIAL_HEADER_NAME: self._credential},
        )

    async def check_entitlement(self, user_id: uuid.UUID) -> bool:
        breaker = await self._breaker_factory.get_breaker(CIRCUIT_NAME)
        try:
            async with breaker:
                response = await self._get(user_id)
                if response.status_code >= 500:
                    response.raise_for_status()
        except OpenedState as exc:
            raise EntitlementCheckUnavailableError(
                "billing-service entitlement-check circuit is open."
            ) from exc
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            raise EntitlementCheckUnavailableError(
                f"billing-service entitlement-check call failed: {exc}"
            ) from exc

        if response.status_code in (401, 403):
            raise EntitlementCheckUnavailableError(
                f"billing-service rejected the entitlement-check credential ({response.status_code})."
            )
        response.raise_for_status()

        body = response.json()
        return bool(body["entitled"])

    async def aclose(self) -> None:
        await self._http.aclose()
