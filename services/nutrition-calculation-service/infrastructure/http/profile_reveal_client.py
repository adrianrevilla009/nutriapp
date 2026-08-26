"""ProfileRevealClient -- implements ProfileRevealPort. Synchronous HTTP
call to profile-service's internal reveal endpoint (implementation plan
Addendum 1): `POST /internal/v1/profile/{user_id}/reveal-metrics`, with the
per-caller service credential sent as a header (Addendum 1 security
sub-addendum requirement 1 -- this client only ever SENDS the credential;
it has no knowledge of how profile-service verifies it).

Resilience (`.claude/skills/resilience-patterns/SKILL.md`, Addendum 1
security sub-addendum requirement 7): a DEDICATED `purgatory` circuit
breaker (`fail_max=5`, `reset_timeout=30s`) -- never shared with
profile-service's own internal KMS breaker -- wraps a `tenacity` retry
(3 attempts, exponential backoff with jitter, only for transient transport
errors -- this call is idempotent, a read with no side effect) and an
explicit timeout (2s connect / 5s read). Own, isolated `httpx.AsyncClient`
connection pool (bulkhead), never shared with any other outbound client.

Only a genuine service-health signal (a transport failure or a 5xx
response) counts toward the breaker's failure threshold -- a 404 ("no
recorded metrics yet"), 401/403 (bad credential), or 429 (rate limited) is
a normal, well-formed business response, not a health signal, and must
not itself trip the breaker.

On circuit-open or persistent failure, raises `ProfileRevealUnavailableError`
-- the caller (`RecomputeNutritionTargetHandler`) must defer the recompute
cleanly, never guess or default a biometric value.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import purgatory
from purgatory.domain.model import OpenedState
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from domain.ports.profile_reveal_port import ProfileRevealUnavailableError, RevealedMetrics
from domain.value_objects.activity_level import ActivityLevel
from domain.value_objects.goal_type import GoalType
from domain.value_objects.sex import Sex

CIRCUIT_NAME = "profile_reveal"
DEFAULT_FAIL_MAX = 5
DEFAULT_RESET_TIMEOUT_SECONDS = 30
CREDENTIAL_HEADER_NAME = "X-Nutrition-Calc-Reveal-Credential"
_REQUIRED_FIELDS = ("weight_kg", "height_cm", "age", "sex", "activity_level", "goal_type")


class ProfileRevealClient:
    """Implements domain.ports.profile_reveal_port.ProfileRevealPort."""

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
    async def _post(self, user_id: uuid.UUID) -> httpx.Response:
        return await self._http.post(
            f"{self._base_url}/internal/v1/profile/{user_id}/reveal-metrics",
            headers={CREDENTIAL_HEADER_NAME: self._credential},
        )

    async def reveal(self, user_id: uuid.UUID) -> RevealedMetrics:
        breaker = await self._breaker_factory.get_breaker(CIRCUIT_NAME)
        try:
            async with breaker:
                response = await self._post(user_id)
                if response.status_code >= 500:
                    response.raise_for_status()
        except OpenedState as exc:
            raise ProfileRevealUnavailableError(
                "profile-service reveal-metrics circuit is open; deferring recompute."
            ) from exc
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            raise ProfileRevealUnavailableError(
                f"profile-service reveal-metrics call failed: {exc}"
            ) from exc

        if response.status_code == 404:
            raise ProfileRevealUnavailableError(
                f"No recorded metrics for user {user_id} yet (404)."
            )
        if response.status_code in (401, 403):
            raise ProfileRevealUnavailableError(
                f"profile-service rejected the reveal credential ({response.status_code})."
            )
        if response.status_code == 429:
            raise ProfileRevealUnavailableError(
                "profile-service reveal-metrics rate limit exceeded (429)."
            )
        response.raise_for_status()

        body: dict[str, Any] = response.json()
        missing = [field for field in _REQUIRED_FIELDS if field not in body]
        if missing:
            raise ProfileRevealUnavailableError(
                f"profile-service reveal-metrics response missing field(s): {missing}."
            )

        return RevealedMetrics(
            weight_kg=body["weight_kg"],
            height_cm=body["height_cm"],
            age=body["age"],
            sex=Sex(body["sex"]),
            activity_level=ActivityLevel(body["activity_level"]),
            goal_type=GoalType(body["goal_type"]),
        )

    async def aclose(self) -> None:
        await self._http.aclose()
