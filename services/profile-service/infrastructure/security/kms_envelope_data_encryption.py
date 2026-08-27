"""KmsEnvelopeDataEncryption -- implements DataEncryptionPort.

Per-user envelope encryption (implementation plan Addendum 1):
  1. Each user gets one AWS KMS-wrapped Data Encryption Key (DEK), stored
     in `profile_data_keys` (infrastructure/persistence/models.py) --
     generated once via KMS GenerateDataKey, never stored in plaintext.
  2. Individual field values (weight_kg, body-metric value, goal
     target_value) are encrypted/decrypted LOCALLY with the unwrapped
     plaintext DEK (AES-256-GCM), not via a per-field KMS round trip --
     KMS is only called to generate a new DEK (first use for a user) or to
     unwrap ("Decrypt") an existing wrapped DEK.
  3. This is profile-service's only synchronous external dependency
     (implementation plan section 7) -- every KMS call goes through a
     dedicated circuit breaker (pybreaker), a bounded retry (tenacity),
     and an explicit timeout (resilience-patterns SKILL.md). Configured
     fail_max/reset_timeout/timeout values are documented in
     profile-service/README.md.
  4. First-use DEK generation is safe under concurrency: two concurrent
     first-use requests for the same brand-new user_id both racing to
     insert a row into `profile_data_keys` converge on exactly one stored
     key (`_store_wrapped_key`'s `ON CONFLICT (user_id) DO NOTHING` +
     re-read-on-conflict path below), never two different keys or an
     unhandled IntegrityError.

Unwrapped plaintext DEKs are cached in-process, per instance, for the
lifetime of the process (never persisted) -- avoids a KMS round trip on
every single field encrypt/decrypt within the same request/handler call.

Timeout composition (resilience-patterns SKILL.md, fixed after
/implementation-review flagged the original composition): this
constructor's `call_timeout_seconds` (default `DEFAULT_OVERALL_TIMEOUT_SECONDS`,
9.0s) bounds the WHOLE breaker-wrapped retry sequence (up to 3 attempts +
up to 2 backoff waits of `wait_exponential_jitter(initial=0.1, max=1.0)`
each) via the single `asyncio.wait_for` around `breaker(retrying(fn))` in
`_call_kms` below -- not a single attempt, despite the name (kept for
backward compatibility with existing call sites/tests that already pass it
explicitly, e.g. to force a short timeout in a test). A single real
attempt's own bound is enforced separately, at the injected `kms_client`'s
own construction site (`infrastructure/composition_root.py`, via
`botocore.config.Config(connect_timeout=DEFAULT_CALL_TIMEOUT_SECONDS,
read_timeout=DEFAULT_CALL_TIMEOUT_SECONDS)`, 2.0s) -- a fake/test client is
free to ignore that config entirely (see
`tests/integration/infrastructure/test_kms_envelope_data_encryption.py`'s
`FakeKmsClient`, which does, so its own tests pass an explicit short
`call_timeout_seconds` to exercise the wait_for path directly).

The overall bound must comfortably exceed
`3 * DEFAULT_CALL_TIMEOUT_SECONDS + 2 * 1.0` (worst case: 3 attempts each
bounded by the per-attempt timeout, plus two maximal backoff waits) or a
genuine retry-exhaustion failure gets reported as a bare timeout instead of
surfacing after retries actually ran -- this was the original bug (a 2.0s
overall timeout could not contain 3 retries plus backoff, and no per-attempt
bound existed at all, so even a single slow call could starve every retry
attempt). With the defaults below (2.0s/attempt, 9.0s overall): worst case
is `3*2.0 + 2*1.0 = 8.0s`, leaving a 1.0s margin.
"""

from __future__ import annotations

import asyncio
import base64
import os
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import pybreaker
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from infrastructure.persistence.models import ProfileDataKeyModel

DEFAULT_FAIL_MAX = 5
DEFAULT_RESET_TIMEOUT_SECONDS = 30
DEFAULT_CALL_TIMEOUT_SECONDS = 2.0
DEFAULT_OVERALL_TIMEOUT_SECONDS = 9.0
DEK_SPEC = "AES_256"


class KmsCallFailedError(Exception):
    """Raised when a KMS call fails (including a timeout) after retries
    are exhausted -- counts as one failure toward the circuit breaker."""


class KmsCircuitOpenError(Exception):
    """Raised instead of blocking when the KMS circuit breaker is open --
    callers get a typed, fail-fast exception, never an unbounded wait."""


class KmsEnvelopeDataEncryption:
    """Implements domain.ports.data_encryption_port.DataEncryptionPort."""

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        kms_client: Any,
        kms_key_id: str,
        fail_max: int = DEFAULT_FAIL_MAX,
        reset_timeout_seconds: int = DEFAULT_RESET_TIMEOUT_SECONDS,
        call_timeout_seconds: float = DEFAULT_OVERALL_TIMEOUT_SECONDS,
    ) -> None:
        self._session_factory = session_factory
        self._kms = kms_client
        self._kms_key_id = kms_key_id
        # NOTE: despite the name (kept for backward-compat with existing
        # call sites/tests), this bounds the WHOLE breaker+retry sequence
        # via asyncio.wait_for below, not a single attempt -- see the
        # module docstring's "Timeout composition" note. A single real
        # attempt's bound comes from the injected kms_client's own
        # configuration (botocore.config.Config(connect_timeout=...,
        # read_timeout=...), set in infrastructure/composition_root.py),
        # which a fake/test client is free to ignore.
        self._call_timeout_seconds = call_timeout_seconds
        self._breaker = pybreaker.CircuitBreaker(
            fail_max=fail_max, reset_timeout=reset_timeout_seconds
        )
        self._dek_cache: dict[str, bytes] = {}

    async def encrypt(self, user_id: uuid.UUID, plaintext: str) -> str:
        dek = await self._get_plaintext_dek(user_id)
        nonce = os.urandom(12)
        ciphertext = AESGCM(dek).encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ciphertext).decode("ascii")

    async def decrypt(self, user_id: uuid.UUID, ciphertext: str) -> str:
        dek = await self._get_plaintext_dek(user_id)
        raw = base64.b64decode(ciphertext.encode("ascii"))
        nonce, encrypted = raw[:12], raw[12:]
        plaintext = AESGCM(dek).decrypt(nonce, encrypted, None)
        return plaintext.decode("utf-8")

    async def _get_plaintext_dek(self, user_id: uuid.UUID) -> bytes:
        cache_key = str(user_id)
        cached = self._dek_cache.get(cache_key)
        if cached is not None:
            return cached

        wrapped = await self._load_wrapped_key(user_id)
        if wrapped is None:
            plaintext_dek, wrapped_ciphertext = await self._kms_generate_data_key()
            stored_wrapped = await self._store_wrapped_key(user_id, wrapped_ciphertext)
            if stored_wrapped != wrapped_ciphertext:
                # Lost a concurrent first-use race: another request's
                # insert for this same brand-new user_id won between our
                # load-miss above and our own insert attempt. Unwrap
                # THEIR stored key instead of the one we just generated,
                # so every concurrent caller converges on the same DEK
                # rather than each unwrapping a different one.
                plaintext_dek = await self._kms_decrypt(stored_wrapped)
        else:
            plaintext_dek = await self._kms_decrypt(wrapped)

        self._dek_cache[cache_key] = plaintext_dek
        return plaintext_dek

    async def _load_wrapped_key(self, user_id: uuid.UUID) -> bytes | None:
        session: AsyncSession
        async with self._session_factory() as session:
            row = await session.get(ProfileDataKeyModel, user_id)
            if row is None:
                return None
            return base64.b64decode(row.wrapped_data_key.encode("ascii"))

    async def _store_wrapped_key(self, user_id: uuid.UUID, wrapped_ciphertext: bytes) -> bytes:
        """Inserts this user's first wrapped DEK, `ON CONFLICT (user_id)
        DO NOTHING` -- two concurrent first-use requests for the same
        brand-new user_id may both reach here after both saw no existing
        row (`_load_wrapped_key` returned None for both). Only one insert
        wins; the loser must not raise (no unhandled IntegrityError) and
        must not silently keep using the key it generated locally but
        failed to persist -- it re-reads the winning row instead. Returns
        the wrapped ciphertext that ended up actually persisted (ours, if
        we won; the other request's, if we lost)."""
        encoded = base64.b64encode(wrapped_ciphertext).decode("ascii")
        session: AsyncSession
        async with self._session_factory() as session:
            stmt = (
                pg_insert(ProfileDataKeyModel)
                .values(
                    user_id=user_id,
                    wrapped_data_key=encoded,
                    kms_key_id=self._kms_key_id,
                    created_at=datetime.now(timezone.utc),
                )
                .on_conflict_do_nothing(index_elements=["user_id"])
                .returning(ProfileDataKeyModel.wrapped_data_key)
            )
            result = await session.execute(stmt)
            inserted_row = result.first()
            await session.commit()
            if inserted_row is not None:
                return wrapped_ciphertext

            # Conflict -- someone else's insert won. Re-read their row.
            existing = await session.get(ProfileDataKeyModel, user_id)
            assert existing is not None, "ON CONFLICT fired, so a row for this user_id must exist."
            return base64.b64decode(existing.wrapped_data_key.encode("ascii"))

    async def _kms_generate_data_key(self) -> tuple[bytes, bytes]:
        response = await self._call_kms(self._raw_generate_data_key)
        return bytes(response["Plaintext"]), bytes(response["CiphertextBlob"])

    async def _kms_decrypt(self, ciphertext_blob: bytes) -> bytes:
        response = await self._call_kms(self._raw_decrypt, ciphertext_blob)
        return bytes(response["Plaintext"])

    def _raw_generate_data_key(self) -> dict[str, Any]:
        return self._kms.generate_data_key(KeyId=self._kms_key_id, KeySpec=DEK_SPEC)  # type: ignore[no-any-return]

    def _raw_decrypt(self, ciphertext_blob: bytes) -> dict[str, Any]:
        return self._kms.decrypt(CiphertextBlob=ciphertext_blob, KeyId=self._kms_key_id)  # type: ignore[no-any-return]

    async def _call_kms(self, fn: Callable[..., dict[str, Any]], *args: bytes) -> dict[str, Any]:
        try:
            protected = self._breaker(_retrying(fn))
            return await asyncio.wait_for(
                asyncio.to_thread(protected, *args), timeout=self._call_timeout_seconds
            )
        except pybreaker.CircuitBreakerError as exc:
            raise KmsCircuitOpenError("KMS circuit breaker is open.") from exc
        except TimeoutError as exc:
            raise KmsCallFailedError("KMS call timed out.") from exc
        except Exception as exc:
            raise KmsCallFailedError(f"KMS call failed: {exc}") from exc


def _retrying(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.1, max=1.0),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def wrapped(*args: bytes) -> dict[str, Any]:
        return fn(*args)

    return wrapped
