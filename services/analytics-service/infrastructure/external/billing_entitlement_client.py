"""analytics-service's own `EntitlementCheckPort` adapter -- the
synchronous fallback `application/entitlement_check.py`'s
`is_user_entitled` reaches for only on a genuine
`EntitlementCacheRepositoryPort` cache miss, never called speculatively.

Talks to billing-service's internal, non-Kong-routed
`GET /internal/v1/billing/entitlements/{user_id}` over the same shared
`X-Internal-Service-Credential` mechanism every other internal-endpoint
consumer in this codebase uses. Own dedicated `purgatory` breaker named
`billing_entitlement_check` -- never shared with any other integration
this service adds later (CLAUDE.md section 2.6). Structurally identical
to `recipe-service`'s/`social-service`'s client of the same name."""

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

_UNAUTHENTICATED_STATUS_CODES = frozenset({401, 403})


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
        self._http = http_client or self._default_http_client()
        self._breaker_factory = purgatory.AsyncCircuitBreakerFactory(
            default_threshold=fail_max, default_ttl=reset_timeout_seconds
        )

    @staticmethod
    def _default_http_client() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(connect=2.0, read=5.0, write=2.0, pool=2.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

    def _entitlement_url(self, user_id: uuid.UUID) -> str:
        return f"{self._base_url}/internal/v1/billing/entitlements/{user_id}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.2, max=2.0),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def _get(self, user_id: uuid.UUID) -> httpx.Response:
        return await self._http.get(
            self._entitlement_url(user_id),
            headers={CREDENTIAL_HEADER_NAME: self._credential},
        )

    async def _call_billing_service(self, user_id: uuid.UUID) -> httpx.Response:
        breaker = await self._breaker_factory.get_breaker(CIRCUIT_NAME)
        async with breaker:
            response = await self._get(user_id)
            if response.status_code >= 500:
                response.raise_for_status()
            return response

    async def check_entitlement(self, user_id: uuid.UUID) -> bool:
        try:
            response = await self._call_billing_service(user_id)
        except OpenedState as exc:
            raise EntitlementCheckUnavailableError(
                "billing-service entitlement-check circuit is open."
            ) from exc
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            raise EntitlementCheckUnavailableError(
                f"billing-service entitlement-check call failed: {exc}"
            ) from exc

        if response.status_code in _UNAUTHENTICATED_STATUS_CODES:
            raise EntitlementCheckUnavailableError(
                f"billing-service rejected the entitlement-check credential ({response.status_code})."
            )
        response.raise_for_status()

        return bool(response.json()["entitled"])

    async def aclose(self) -> None:
        await self._http.aclose()
