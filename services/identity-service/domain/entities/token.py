"""Token entities: revocable refresh tokens, and single-use secret-reference
tokens (email verification / password reset), per ADR-0022's two-token-type
signing scheme and the reference+secret pattern in the implementation plan
section 5.

Zero framework imports (ADR-0001). Clocks are always passed in explicitly
(never `datetime.now()` inside these methods) so tests can control time
without real sleeping, per the approved test plan.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class TokenExpiredError(Exception):
    """Raised when an expired token is used, revealed, or verified."""


class TokenAlreadyUsedError(Exception):
    """Raised on a second consumption attempt of a single-use secret token."""


class TokenAlreadyRevealedError(Exception):
    """Raised on a second reveal attempt of a secret-reference token (replay defense)."""


class TokenRevokedError(Exception):
    """Raised when a revoked refresh token is presented."""


class TokenSecretMismatchError(Exception):
    """Raised when a submitted secret does not match the stored token's secret hash."""


class SecretTokenKind(str, Enum):
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
    PASSWORD_RESET = "PASSWORD_RESET"


@dataclass(slots=True)
class RefreshToken:
    """A server-side-tracked, individually revocable refresh token (ADR-0022).

    Opaque to every service but identity-service itself — never a JWT.
    """

    token_id: uuid.UUID
    user_id: uuid.UUID
    token_hash: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def revoke(self, now: datetime) -> None:
        """Idempotent: revoking an already-revoked token is a no-op."""
        if self.revoked_at is None:
            self.revoked_at = now

    def ensure_usable(self, now: datetime) -> None:
        """Raises if this token cannot currently be exchanged for an access token."""
        if self.is_revoked():
            raise TokenRevokedError("Refresh token has been revoked.")
        if self.is_expired(now):
            raise TokenExpiredError("Refresh token has expired.")


@dataclass(slots=True)
class SecretReferenceToken:
    """A single-use secret token addressed by a public `reference_id`.

    The raw secret is what the end user redeems (via an emailed link); the
    reference id is what travels in domain events and in the internal
    reveal-endpoint URL, per the reference+secret pattern (implementation
    plan section 5) so the raw secret never appears in a published event.

    `secret_hash` supports verifying a user-submitted secret without
    storing it in comparable plaintext. `raw_secret` is retained only until
    the one-time internal `reveal()` call, after which it is cleared
    (crypto-shredded) — the persistence adapter must null the backing
    column at that point too.
    """

    reference_id: uuid.UUID
    user_id: uuid.UUID
    kind: SecretTokenKind
    secret_hash: str
    created_at: datetime
    expires_at: datetime
    raw_secret: str | None = None
    revealed_at: datetime | None = None
    used_at: datetime | None = None

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def reveal(self, now: datetime) -> str:
        """One-time retrieval of the raw secret, for the internal reveal endpoint."""
        if self.is_expired(now):
            raise TokenExpiredError("Token has expired.")
        if self.revealed_at is not None:
            raise TokenAlreadyRevealedError("Token secret has already been revealed.")
        if self.raw_secret is None:
            raise TokenAlreadyRevealedError("Token secret is no longer available.")
        secret = self.raw_secret
        self.revealed_at = now
        self.raw_secret = None
        return secret

    def verify_and_mark_used(self, candidate_secret_hash: str, now: datetime) -> None:
        """Consumes the token as part of verify-email / confirm-password-reset."""
        if self.used_at is not None:
            raise TokenAlreadyUsedError("Token has already been used.")
        if self.is_expired(now):
            raise TokenExpiredError("Token has expired.")
        if candidate_secret_hash != self.secret_hash:
            raise TokenSecretMismatchError("Token secret does not match.")
        self.used_at = now
