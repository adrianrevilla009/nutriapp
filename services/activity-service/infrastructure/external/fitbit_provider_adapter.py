"""FitbitProviderAdapter -- implements WearableProviderPort for Fitbit,
per the implementation plan's 2026-09-11 addendum (Fitbit adapter,
mocked, no real credentials, approved).

Built against Fitbit's real, publicly documented API contract:
- OAuth 2.0 Authorization Code Grant flow / token refresh:
  https://dev.fitbit.com/build/reference/web-api/authorization/
  POST https://api.fitbit.com/oauth2/token, form-urlencoded,
  Authorization: Basic base64(client_id:client_secret).
- Token revocation:
  https://dev.fitbit.com/build/reference/web-api/authorization/revoke-token/
  POST https://api.fitbit.com/oauth2/revoke.
- Activity Logs List:
  https://dev.fitbit.com/build/reference/web-api/activity/get-activity-log-list/
  GET https://api.fitbit.com/1/user/-/activities/list.json.

Same "build against real public docs, test only against fixtures" approach
as billing-service's StripePaymentAdapter -- no real Fitbit developer
account exists in this environment, so this adapter is exercised
exclusively via httpx.MockTransport fixtures in
tests/integration/infrastructure/test_fitbit_provider_adapter.py, never a
live call.

Resilience (.claude/skills/resilience-patterns/SKILL.md):
- TWO dedicated purgatory circuit breakers, not one shared breaker --
  CIRCUIT_NAME_OAUTH guards the token-exchange/refresh/revoke calls
  (Fitbit's OAuth token endpoint), CIRCUIT_NAME_SYNC guards the activity
  sync fetch (Fitbit's resource API) -- an outage in one must not trip the
  breaker guarding the other.
- Deliberately NO tenacity retry on token exchange or token refresh. Both
  grants are single-use: Fitbit invalidates the presented
  authorization_code (exchange) or refresh_token (refresh) the moment it
  is accepted, and issues a new refresh token on every refresh. If the
  HTTP response is lost after Fitbit accepted the request server-side (a
  transient network failure on the way back), blindly retrying with the
  same, now-already-consumed code/token would fail with invalid_grant and
  could force the user to re-authorize. This is exactly
  resilience-patterns SKILL.md's "never retry a non-idempotent operation
  ... without a deduplication key" rule -- neither grant carries one.
- sync()'s activity fetch IS retried (tenacity, 3 attempts, exponential
  backoff+jitter, transport errors only) -- a GET with no side effect,
  safe to retry, mirroring ClaudeVisionAdapter's analyze().
- Own, dedicated httpx.AsyncClient (bulkhead), explicit timeout
  (connect=3s / read=10s -- tunable via constructor, not hardcoded past
  these defaults).

OAuth token handling (docs/secrets-management.md,
.claude/agents/activity-agent.md): tokens are never logged (this module
never logs a WearableOAuthTokens instance or a raw token string -- only
structlog.warning on a failed revoke call, which logs the exception only,
not the token) and are persisted exclusively through the injected
WearableTokenStorePort (InMemoryWearableTokenStore for this pass -- see
that module's docstring for why a durable, encrypted-at-rest store is
deferred).

Disconnection (.claude/agents/activity-agent.md's "honored immediately"
rule): disconnect() deletes the local token-store record BEFORE
attempting the outbound revoke call, and does not raise if the revoke
call itself fails -- local sync capability is removed unconditionally and
immediately; the best-effort remote revoke is a courtesy to Fitbit, not a
precondition for the local effect.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import purgatory
import structlog
from purgatory.domain.model import OpenedState
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from domain.ports.wearable_provider_port import (
    WearableConnectionNotFoundError,
    WearableProviderUnavailableError,
    WearableSyncResult,
)
from domain.ports.wearable_token_store_port import WearableTokenStorePort
from domain.value_objects.calories_burned import CaloriesBurned
from domain.value_objects.duration_minutes import DurationMinutes
from domain.value_objects.exercise_type import ExerciseType
from domain.value_objects.wearable_oauth_tokens import WearableOAuthTokens

logger = structlog.get_logger()

PROVIDER_NAME = "fitbit"

CIRCUIT_NAME_OAUTH = "fitbit_oauth"
CIRCUIT_NAME_SYNC = "fitbit_activities_sync"
DEFAULT_FAIL_MAX = 5
DEFAULT_RESET_TIMEOUT_SECONDS = 30

# Fitbit's own documented activity names (a small, non-exhaustive sample of
# the most common ones) mapped onto this domain's closed ExerciseType enum
# -- anything unrecognized maps to OTHER with the raw Fitbit name preserved
# only in `label`, never folded into the enum (same rule as manually
# logged entries' ExerciseType.OTHER/label split).
_ACTIVITY_NAME_TO_EXERCISE_TYPE: dict[str, ExerciseType] = {
    "run": ExerciseType.RUNNING,
    "running": ExerciseType.RUNNING,
    "walk": ExerciseType.WALKING,
    "walking": ExerciseType.WALKING,
    "bike": ExerciseType.CYCLING,
    "biking": ExerciseType.CYCLING,
    "cycling": ExerciseType.CYCLING,
    "swim": ExerciseType.SWIMMING,
    "swimming": ExerciseType.SWIMMING,
    "weights": ExerciseType.STRENGTH_TRAINING,
    "weight training": ExerciseType.STRENGTH_TRAINING,
    "strength training": ExerciseType.STRENGTH_TRAINING,
}


def _map_activity_name(name: str) -> tuple[ExerciseType, str | None]:
    exercise_type = _ACTIVITY_NAME_TO_EXERCISE_TYPE.get(name.strip().lower())
    if exercise_type is None:
        return ExerciseType.OTHER, name
    return exercise_type, None


def _basic_auth_header(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}".encode()
    return f"Basic {base64.b64encode(raw).decode('ascii')}"


class FitbitProviderAdapter:
    """Implements domain.ports.wearable_provider_port.WearableProviderPort."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        token_store: WearableTokenStorePort,
        base_url: str = "https://api.fitbit.com",
        http_client: httpx.AsyncClient | None = None,
        fail_max: int = DEFAULT_FAIL_MAX,
        reset_timeout_seconds: float = DEFAULT_RESET_TIMEOUT_SECONDS,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._token_store = token_store
        self._base_url = base_url.rstrip("/")
        self._http = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(connect=3.0, read=10.0, write=3.0, pool=3.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        self._breaker_factory = purgatory.AsyncCircuitBreakerFactory(
            default_threshold=fail_max, default_ttl=reset_timeout_seconds
        )

    # ------------------------------------------------------------------
    # WearableProviderPort
    # ------------------------------------------------------------------

    async def connect(self, user_id: uuid.UUID, authorization_code: str) -> None:
        breaker = await self._breaker_factory.get_breaker(CIRCUIT_NAME_OAUTH)
        try:
            async with breaker:
                response = await self._exchange_authorization_code(authorization_code)
        except OpenedState as exc:
            raise WearableProviderUnavailableError("Fitbit OAuth circuit is open.") from exc
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            raise WearableProviderUnavailableError(
                f"Fitbit token exchange connection error: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise WearableProviderUnavailableError(
                f"Fitbit rejected the authorization code ({response.status_code})."
            )

        tokens = _parse_token_response(response.json())
        await self._token_store.save(user_id, PROVIDER_NAME, tokens)

    async def sync(self, user_id: uuid.UUID, since: datetime) -> list[WearableSyncResult]:
        tokens = await self._ensure_fresh_tokens(user_id)

        breaker = await self._breaker_factory.get_breaker(CIRCUIT_NAME_SYNC)
        try:
            async with breaker:
                response = await self._fetch_activities(tokens.access_token, since)
        except OpenedState as exc:
            raise WearableProviderUnavailableError(
                "Fitbit activity-sync circuit is open."
            ) from exc
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            raise WearableProviderUnavailableError(
                f"Fitbit activity sync connection error: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise WearableProviderUnavailableError(
                f"Fitbit rejected the activity sync request ({response.status_code})."
            )

        return _parse_activities_response(response.json())

    async def disconnect(self, user_id: uuid.UUID) -> None:
        tokens = await self._token_store.get(user_id, PROVIDER_NAME)
        if tokens is None:
            return  # Idempotent no-op -- never connected or already disconnected.

        # Immediate local effect FIRST (module docstring) -- a subsequent
        # sync() call must fail closed regardless of whether the remote
        # revoke below succeeds.
        await self._token_store.delete(user_id, PROVIDER_NAME)

        breaker = await self._breaker_factory.get_breaker(CIRCUIT_NAME_OAUTH)
        try:
            async with breaker:
                await self._revoke(tokens.access_token)
        except OpenedState:
            logger.warning("fitbit_revoke_circuit_open", user_id=str(user_id))
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            logger.warning("fitbit_revoke_failed", user_id=str(user_id), error=str(exc))

    # ------------------------------------------------------------------
    # Internal HTTP calls
    # ------------------------------------------------------------------

    async def _exchange_authorization_code(self, authorization_code: str) -> httpx.Response:
        """Deliberately NOT decorated with @retry -- see module docstring:
        an authorization code is single-use."""
        headers = {"Authorization": _basic_auth_header(self._client_id, self._client_secret)}
        form_body = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self._redirect_uri,
            "client_id": self._client_id,
        }
        return await self._http.post(
            f"{self._base_url}/oauth2/token", data=form_body, headers=headers
        )

    async def _refresh(self, refresh_token: str) -> httpx.Response:
        """Deliberately NOT decorated with @retry -- see module docstring:
        Fitbit rotates (invalidates) the presented refresh token on every
        use."""
        headers = {"Authorization": _basic_auth_header(self._client_id, self._client_secret)}
        form_body = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        return await self._http.post(
            f"{self._base_url}/oauth2/token", data=form_body, headers=headers
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.2, max=2.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _fetch_activities(self, access_token: str, since: datetime) -> httpx.Response:
        """A read with no side effect -- safe to retry on transient
        transport failures, unlike the OAuth calls above."""
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "afterDate": since.date().isoformat(),
            "sort": "asc",
            "offset": "0",
            "limit": "100",
        }
        return await self._http.get(
            f"{self._base_url}/1/user/-/activities/list.json",
            params=params,
            headers=headers,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.2, max=2.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _revoke(self, access_token: str) -> httpx.Response:
        """Revoking a token is effectively idempotent (revoking an
        already-invalid token is not a dangerous retry the way consuming a
        single-use grant is) -- safe to retry on transient failures."""
        return await self._http.post(
            f"{self._base_url}/oauth2/revoke",
            data={"token": access_token},
        )

    async def _ensure_fresh_tokens(self, user_id: uuid.UUID) -> WearableOAuthTokens:
        tokens = await self._token_store.get(user_id, PROVIDER_NAME)
        if tokens is None:
            raise WearableConnectionNotFoundError(
                f"No Fitbit connection found for user {user_id}."
            )
        if not tokens.is_expired(now=datetime.now(timezone.utc)):
            return tokens

        breaker = await self._breaker_factory.get_breaker(CIRCUIT_NAME_OAUTH)
        try:
            async with breaker:
                response = await self._refresh(tokens.refresh_token)
        except OpenedState as exc:
            raise WearableProviderUnavailableError("Fitbit OAuth circuit is open.") from exc
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            raise WearableProviderUnavailableError(
                f"Fitbit token refresh connection error: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise WearableProviderUnavailableError(
                f"Fitbit rejected the refresh token ({response.status_code})."
            )

        refreshed = _parse_token_response(response.json())
        await self._token_store.save(user_id, PROVIDER_NAME, refreshed)
        return refreshed

    async def aclose(self) -> None:
        await self._http.aclose()


def _parse_token_response(body: dict[str, Any]) -> WearableOAuthTokens:
    expires_in_seconds = int(body["expires_in"])
    return WearableOAuthTokens(
        access_token=str(body["access_token"]),
        refresh_token=str(body["refresh_token"]),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds),
    )


def _parse_activities_response(body: dict[str, Any]) -> list[WearableSyncResult]:
    results: list[WearableSyncResult] = []
    for activity in body.get("activities", []):
        exercise_type, label = _map_activity_name(str(activity["name"]))
        duration_ms = int(activity["duration"])
        # Fitbit reports duration in milliseconds; this domain's
        # DurationMinutes is whole, strictly-positive minutes -- round to
        # the nearest minute, floored at 1 (never 0, which DurationMinutes
        # rejects) so a genuinely short logged activity is never dropped.
        duration_minutes = max(1, round(duration_ms / 60000))
        results.append(
            WearableSyncResult(
                provider_activity_id=str(activity["logId"]),
                exercise_type=exercise_type,
                duration=DurationMinutes(duration_minutes),
                # Carried through exactly as Fitbit reports it -- never
                # rounded/interpolated beyond Fitbit's own reported figure.
                calories_burned=CaloriesBurned(float(activity["calories"])),
                started_at=datetime.fromisoformat(str(activity["startTime"])),
                label=label,
            )
        )
    return results
