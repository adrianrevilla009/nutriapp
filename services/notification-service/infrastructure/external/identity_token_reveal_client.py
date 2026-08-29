"""IdentityTokenRevealClient -- implements TokenRevealPort. Synchronous
HTTP call to identity-service's existing internal endpoint
(POST /internal/v1/auth/tokens/{reference_id}/reveal, never routed through
Kong -- see services/identity-service/infrastructure/http/routes/internal_token_routes.py),
sending the internal-reveal-credential header this service is granted
read access to (implementation plan section 6/7).

Resilience (.claude/skills/resilience-patterns/SKILL.md): a DEDICATED
`purgatory` circuit breaker (fail_max=5, reset_timeout=30s) -- never
shared with the SES/SNS breakers -- wraps a `tenacity` retry (3 attempts,
exponential backoff with jitter -- this call never mutates anything on a
retry: identity-service's reveal is a once-only-effective GET-shaped
operation from this caller's point of view) and an explicit timeout (2s
connect / 5s read). Own, isolated httpx.AsyncClient connection pool
(bulkhead).

Only a genuine service-health signal (a transport failure or a 5xx
response) counts toward the breaker's failure threshold -- a 404
("unknown reference id") or 401/403 (bad credential) is a normal,
well-formed business response, not a health signal.
"""

from __future__ import annotations

from typing import Any

import httpx
import purgatory
from purgatory.domain.model import OpenedState
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from domain.ports.token_reveal_port import (
    RevealedToken,
    TokenRevealNotFoundError,
    TokenRevealUnavailableError,
)

CIRCUIT_NAME = "identity_token_reveal"
DEFAULT_FAIL_MAX = 5
DEFAULT_RESET_TIMEOUT_SECONDS = 30
CREDENTIAL_HEADER_NAME = "X-Internal-Service-Credential"


def _parse_revealed_token(body: dict[str, Any]) -> RevealedToken:
    return RevealedToken(secret=body["secret"], user_id=body["user_id"], kind=body["kind"])


class IdentityTokenRevealClient:
    """Implements domain.ports.token_reveal_port.TokenRevealPort."""

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
    async def _post(self, reference_id: str) -> httpx.Response:
        return await self._http.post(
            f"{self._base_url}/internal/v1/auth/tokens/{reference_id}/reveal",
            headers={CREDENTIAL_HEADER_NAME: self._credential},
        )

    async def reveal(self, reference_id: str) -> RevealedToken:
        breaker = await self._breaker_factory.get_breaker(CIRCUIT_NAME)
        try:
            async with breaker:
                response = await self._post(reference_id)
                if response.status_code >= 500:
                    response.raise_for_status()
        except OpenedState as exc:
            raise TokenRevealUnavailableError(
                "identity-service token-reveal circuit is open."
            ) from exc
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            raise TokenRevealUnavailableError(
                f"identity-service reveal call failed: {exc}"
            ) from exc

        if response.status_code == 404:
            raise TokenRevealNotFoundError(f"Unknown token reference id {reference_id!r}.")
        if response.status_code in (400, 401, 403):
            raise TokenRevealNotFoundError(
                f"identity-service rejected the reveal request ({response.status_code})."
            )
        response.raise_for_status()

        return _parse_revealed_token(response.json())

    async def aclose(self) -> None:
        await self._http.aclose()
