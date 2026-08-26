"""GetBiometricSnapshotForCalculationQuery + handler -- backs the internal
`POST /internal/v1/profile/{user_id}/reveal-metrics` endpoint
(implementation plan Addendum 2), called synchronously by
nutrition-calculation-service to obtain plaintext biometric values for its
Mifflin-St Jeor BMR/TDEE calculation. `profile-service` deliberately
isolates its per-user KMS key material to itself (ADR-0023), so no other
service can decrypt these fields on its own.

Response minimization (requirement 5): returns EXACTLY
`weight_kg, height_cm, age, sex, activity_level, goal_type` -- a dedicated
query, not a wrapper around `GetProfileSnapshotHandler` (which also
exposes `consent_granted`, `goal_target_value`, `goal_target_date`, none
of which nutrition-calculation-service's BMR/TDEE formula needs, and the
last two of which are additional Article 9 exposure this endpoint must
not create).

Security posture (requirements 3/4/6/7, not a reuse of
identity-service's single-shared-credential/no-rate-limit/no-audit-trail
`.../reveal` precedent -- a dedicated security-agent review found that
insufficient for repeatedly-callable Article 9 health data disclosure):
  1. Per-caller credential, compared via `hmac.compare_digest` against
     every configured (credential -> actor_id) pair -- never a single
     shared secret, and never a differentiated error message that would
     help an attacker distinguish "wrong secret" from "unknown caller".
  2. Rate limiting keyed by (a hash of) the caller credential + user_id --
     exceeding it raises before the KMS-decrypting port is ever invoked.
  3. Exactly one audit record per call, success or failure -- metadata
     never contains a biometric field VALUE, only field NAMES or a short
     failure `reason` (domain.entities.audit_record.AuditRecord enforces
     this).
  4. A structured log line per call -- user_id, outcome, and (on success)
     the field NAMES revealed, never a numeric/enum VALUE (requirement 7,
     tested by tests/integration/infrastructure/test_reveal_metrics_log_redaction.py).
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

import structlog

from application.errors import (
    InvalidCallerCredentialError,
    ProfileNotFoundError,
    RevealRateLimitedError,
)
from domain.entities.audit_record import AuditRecord
from domain.ports.audit_repository_port import AuditRepositoryPort
from domain.ports.data_encryption_port import DataEncryptionPort
from domain.ports.profile_snapshot_read_port import ProfileSnapshotReadPort
from domain.ports.rate_limiter_port import RateLimiterPort, RateLimitExceededError

logger = structlog.get_logger()

ACTION = "biometric_snapshot_revealed"
TARGET_TYPE = "profile"

# The exact, minimized, allow-listed field set this endpoint may ever
# return -- requirement 5. Never add a field here without a corresponding
# plan addendum (this list is also what gets audited/logged as "fields").
REVEALED_FIELDS: tuple[str, ...] = (
    "weight_kg",
    "height_cm",
    "age",
    "sex",
    "activity_level",
    "goal_type",
)

_ENCRYPTED_NUMERIC_FIELDS = ("weight_kg",)
_ENCRYPTED_BODY_METRIC_FIELDS: dict[str, type] = {
    "height_cm": float,
    "age": int,
    "sex": str,
    "activity_level": str,
}

DEFAULT_REVEAL_RATE_LIMIT = 30
DEFAULT_REVEAL_RATE_LIMIT_WINDOW_SECONDS = 60


@dataclass(frozen=True, slots=True)
class BiometricSnapshotForCalculationDTO:
    weight_kg: float | None
    height_cm: float | None
    age: int | None
    sex: str | None
    activity_level: str | None
    goal_type: str | None


@dataclass(frozen=True, slots=True)
class GetBiometricSnapshotForCalculationQuery:
    user_id: uuid.UUID
    caller_service_credential: str
    correlation_id: str


def _hash_credential(credential: str) -> str:
    """Never use the raw credential value as (part of) a Redis key/log
    line -- a short, non-reversible hash is enough to key the rate limiter
    per-caller without ever persisting/transmitting the secret itself
    anywhere but the original Authorization-style header."""
    return hashlib.sha256(credential.encode("utf-8")).hexdigest()[:16]


class GetBiometricSnapshotForCalculationHandler:
    def __init__(
        self,
        snapshot_read: ProfileSnapshotReadPort,
        encryption: DataEncryptionPort,
        audit_repository: AuditRepositoryPort,
        rate_limiter: RateLimiterPort,
        expected_caller_credentials: Mapping[str, str],
        rate_limit: int = DEFAULT_REVEAL_RATE_LIMIT,
        rate_limit_window_seconds: int = DEFAULT_REVEAL_RATE_LIMIT_WINDOW_SECONDS,
    ) -> None:
        self._snapshot_read = snapshot_read
        self._encryption = encryption
        self._audit = audit_repository
        self._rate_limiter = rate_limiter
        self._expected_caller_credentials = expected_caller_credentials
        self._rate_limit = rate_limit
        self._rate_limit_window_seconds = rate_limit_window_seconds

    async def handle(
        self, query: GetBiometricSnapshotForCalculationQuery
    ) -> BiometricSnapshotForCalculationDTO:
        actor_id = self._resolve_actor(query.caller_service_credential)
        if actor_id is None:
            await self._audit_failure(query, actor_id=None, reason="invalid_caller_credential")
            logger.info(
                "biometric_snapshot_reveal_rejected",
                user_id=str(query.user_id),
                outcome="failure",
                reason="invalid_caller_credential",
            )
            raise InvalidCallerCredentialError("Invalid internal service credential.")

        try:
            await self._rate_limiter.check_and_increment(
                key=self._rate_limit_key(query),
                limit=self._rate_limit,
                window_seconds=self._rate_limit_window_seconds,
            )
        except RateLimitExceededError as exc:
            await self._audit_failure(query, actor_id=actor_id, reason="rate_limited")
            logger.info(
                "biometric_snapshot_reveal_rejected",
                user_id=str(query.user_id),
                outcome="failure",
                reason="rate_limited",
            )
            raise RevealRateLimitedError(
                "Reveal-metrics rate limit exceeded for this caller/user_id."
            ) from exc

        row = await self._snapshot_read.get_snapshot(query.user_id)
        if row is None:
            await self._audit_failure(query, actor_id=actor_id, reason="profile_not_found")
            logger.info(
                "biometric_snapshot_reveal_rejected",
                user_id=str(query.user_id),
                outcome="failure",
                reason="profile_not_found",
            )
            raise ProfileNotFoundError("No profile exists yet for this user_id.")

        decrypted: dict[str, object] = {}
        for field_name in _ENCRYPTED_NUMERIC_FIELDS:
            ciphertext = row.get(field_name)
            decrypted[field_name] = (
                float(await self._encryption.decrypt(query.user_id, ciphertext))
                if ciphertext is not None
                else None
            )
        for field_name, caster in _ENCRYPTED_BODY_METRIC_FIELDS.items():
            ciphertext = row.get(field_name)
            decrypted[field_name] = (
                caster(await self._encryption.decrypt(query.user_id, ciphertext))
                if ciphertext is not None
                else None
            )

        await self._audit.record(
            AuditRecord(
                action=ACTION,
                target_type=TARGET_TYPE,
                target_id=str(query.user_id),
                outcome="success",
                correlation_id=query.correlation_id,
                actor_id=actor_id,
                metadata={"fields": list(REVEALED_FIELDS)},
            )
        )
        logger.info(
            "biometric_snapshot_revealed",
            user_id=str(query.user_id),
            outcome="success",
            fields=list(REVEALED_FIELDS),
        )

        return BiometricSnapshotForCalculationDTO(
            weight_kg=decrypted["weight_kg"],  # type: ignore[arg-type]
            height_cm=decrypted["height_cm"],  # type: ignore[arg-type]
            age=decrypted["age"],  # type: ignore[arg-type]
            sex=decrypted["sex"],  # type: ignore[arg-type]
            activity_level=decrypted["activity_level"],  # type: ignore[arg-type]
            goal_type=row.get("goal_type"),
        )

    def _resolve_actor(self, presented: str) -> str | None:
        for credential, actor_id in self._expected_caller_credentials.items():
            if hmac.compare_digest(presented, credential):
                return actor_id
        return None

    def _rate_limit_key(self, query: GetBiometricSnapshotForCalculationQuery) -> str:
        return (
            "profile:ratelimit:reveal-metrics:"
            f"{_hash_credential(query.caller_service_credential)}:{query.user_id}"
        )

    async def _audit_failure(
        self,
        query: GetBiometricSnapshotForCalculationQuery,
        *,
        actor_id: str | None,
        reason: str,
    ) -> None:
        await self._audit.record(
            AuditRecord(
                action=ACTION,
                target_type=TARGET_TYPE,
                target_id=str(query.user_id),
                outcome="failure",
                correlation_id=query.correlation_id,
                actor_id=actor_id,
                metadata={"reason": reason},
            )
        )
