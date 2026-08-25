"""JwtVerifier -- RS256 JWT verification via a service's published JWKS
endpoint, per ADR-0022 (`docs/adr/0022-token-signing-and-jwks.md`) and
`docs/authorization-model.md` section 2.

Every service downstream of `identity-service` verifies an access token's
signature and expiry *locally* against `identity-service`'s published
`/.well-known/jwks.json` -- never via a synchronous call back to
`identity-service` on every request (that would reintroduce exactly the
coupling the Open Host Service relationship in
`docs/domain-glossary-and-context-map.md` is meant to avoid). This module
is the shared implementation of that verification so each consuming
service doesn't reimplement JWKS-fetch-and-cache logic independently --
`profile-service` is the first consumer
(`services/profile-service/infrastructure/http/dependencies.py`); ADR-0022's
follow-up actions flagged this as a candidate for `packages/shared-contracts`.

Design:
- The JWKS response (public key material only) is fetched over HTTP and
  cached in-process with a bounded TTL (`.claude/skills/caching-strategy/SKILL.md`
  -- explicit TTL, not an unbounded/indefinite cache, since ADR-0022 notes
  key rotation requires periodically refreshing the cached JWKS).
- The JWKS *fetch* is the one synchronous, network-crossing operation here,
  so it gets the full resilience treatment
  (`.claude/skills/resilience-patterns/SKILL.md`): a dedicated circuit
  breaker (`pybreaker`), a bounded `tenacity` retry inside the breaker's
  failure counting, and an explicit per-attempt timeout (the injected
  `httpx.Client`'s own `timeout`) plus an overall timeout bounding the
  whole breaker+retry sequence (see the "Timeout composition" note below --
  mirrors `profile-service`'s `KmsEnvelopeDataEncryption` precedent, fixed
  for the same two-timeouts-not-one reason during this same review pass).
- Verifying an individual token, once the signing key is cached, is a fast
  local operation -- no network call per request.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
import pybreaker
from jwt import PyJWK
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

DEFAULT_JWKS_CACHE_TTL_SECONDS = 600.0  # 10 minutes -- caching-strategy SKILL.md
DEFAULT_FAIL_MAX = 5
DEFAULT_RESET_TIMEOUT_SECONDS = 30
# Per-attempt bound (enforced by the injected httpx.Client's own `timeout`,
# not by this module -- see the module docstring's "Timeout composition"
# note and kms_envelope_data_encryption.py's identical reasoning).
DEFAULT_CALL_TIMEOUT_SECONDS = 2.0
# Overall bound on the whole breaker+retry sequence (up to 3 attempts + up
# to 2 backoff waits of wait_exponential_jitter(initial=0.1, max=1.0) each):
# worst case 3*2.0 + 2*1.0 = 8.0s, so 9.0s leaves a 1.0s margin.
DEFAULT_OVERALL_TIMEOUT_SECONDS = 9.0


class JwtVerificationError(Exception):
    """Raised for a missing/malformed/expired/tampered token, a token
    signed by a `kid` absent from the fetched JWKS, or a token missing a
    required claim (`user_id`). Callers should treat this as
    "unauthenticated" (401), never distinguish the reason to the caller in
    a way that helps an attacker iterate (per authorization-model.md's
    spirit of not leaking enumeration signals)."""


class JwksFetchError(Exception):
    """Raised when fetching the JWKS document fails (including a timeout)
    after retries are exhausted -- counts as one failure toward the
    circuit breaker."""


class JwksCircuitOpenError(Exception):
    """Raised instead of blocking when the JWKS-fetch circuit breaker is
    open -- callers get a typed, fail-fast exception, never an unbounded
    wait."""


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """The verified caller identity extracted from an access token's
    claims (ADR-0022: `user_id` + `roles` only, never raw permissions)."""

    user_id: uuid.UUID
    roles: frozenset[str]


class JwtVerifier:
    """Fetches + caches a JWKS document and verifies RS256 access tokens
    against it. One instance per producing service (e.g. one for
    identity-service's tokens) -- never share a single instance's cache
    across two different JWKS sources."""

    def __init__(
        self,
        jwks_url: str,
        issuer: str | None = None,
        cache_ttl_seconds: float = DEFAULT_JWKS_CACHE_TTL_SECONDS,
        fail_max: int = DEFAULT_FAIL_MAX,
        reset_timeout_seconds: int = DEFAULT_RESET_TIMEOUT_SECONDS,
        call_timeout_seconds: float = DEFAULT_CALL_TIMEOUT_SECONDS,
        overall_timeout_seconds: float = DEFAULT_OVERALL_TIMEOUT_SECONDS,
        http_client: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._jwks_url = jwks_url
        self._issuer = issuer
        self._cache_ttl_seconds = cache_ttl_seconds
        self._overall_timeout_seconds = overall_timeout_seconds
        self._breaker = pybreaker.CircuitBreaker(
            fail_max=fail_max, reset_timeout=reset_timeout_seconds
        )
        self._http_client = http_client or httpx.Client(timeout=call_timeout_seconds)
        self._clock = clock
        self._cached_keys: dict[str, Any] = {}
        self._cached_at: float | None = None

    async def verify(self, token: str) -> AuthenticatedPrincipal:
        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            raise JwtVerificationError("Malformed token header.") from exc

        kid = unverified_header.get("kid")
        if not kid:
            raise JwtVerificationError("Token header is missing 'kid'.")

        key = await self._get_signing_key(kid)

        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                issuer=self._issuer,
                options={"require": ["exp", "iat"]},
            )
        except jwt.InvalidTokenError as exc:
            raise JwtVerificationError(f"Token verification failed: {exc}") from exc

        raw_user_id = claims.get("user_id")
        if not raw_user_id:
            raise JwtVerificationError("Token is missing the 'user_id' claim.")
        try:
            user_id = uuid.UUID(str(raw_user_id))
        except ValueError as exc:
            raise JwtVerificationError("Token 'user_id' claim is not a valid UUID.") from exc

        roles = frozenset(claims.get("roles") or [])
        return AuthenticatedPrincipal(user_id=user_id, roles=roles)

    async def _get_signing_key(self, kid: str) -> Any:
        if self._cached_at is not None:
            age = self._clock() - self._cached_at
            if age < self._cache_ttl_seconds and kid in self._cached_keys:
                return self._cached_keys[kid]

        await self._refresh_jwks()

        if kid not in self._cached_keys:
            raise JwtVerificationError(f"Unknown signing key id: {kid!r}")
        return self._cached_keys[kid]

    async def _refresh_jwks(self) -> None:
        jwks_document = await self._fetch_jwks()
        keys: dict[str, Any] = {}
        for jwk_dict in jwks_document.get("keys", []):
            key_id = jwk_dict.get("kid")
            if not key_id:
                continue
            keys[key_id] = PyJWK.from_dict(jwk_dict).key
        self._cached_keys = keys
        self._cached_at = self._clock()

    async def _fetch_jwks(self) -> dict[str, Any]:
        try:
            protected = self._breaker(_retrying(self._raw_fetch))
            return await asyncio.wait_for(
                asyncio.to_thread(protected), timeout=self._overall_timeout_seconds
            )
        except pybreaker.CircuitBreakerError as exc:
            raise JwksCircuitOpenError("JWKS-fetch circuit breaker is open.") from exc
        except TimeoutError as exc:
            raise JwksFetchError(
                "JWKS fetch timed out (possibly after exhausting retries)."
            ) from exc
        except Exception as exc:
            raise JwksFetchError(f"JWKS fetch failed: {exc}") from exc

    def _raw_fetch(self) -> dict[str, Any]:
        response = self._http_client.get(self._jwks_url)
        response.raise_for_status()
        return response.json()


def _retrying(fn):
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.1, max=1.0),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def wrapped(*args):
        return fn(*args)

    return wrapped
