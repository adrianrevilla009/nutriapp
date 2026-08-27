"""Application-layer error types.

These are deliberately generic where the domain-level error would leak
information useful for enumeration (CLAUDE.md / implementation plan
acceptance criterion 3: no user-enumeration signal). The *specific* reason
is only ever written to the audit trail, never returned to the caller.
"""

from __future__ import annotations


class InvalidCredentialsError(Exception):
    """Generic login failure — covers wrong password, unknown email,
    unverified account, and locked account alike, from the caller's point
    of view."""


class InvalidTokenError(Exception):
    """Generic token-redemption failure — covers unknown, expired, and
    already-used tokens alike, from the caller's point of view (applies to
    verify-email and password-reset confirm)."""


class RateLimitedError(Exception):
    """Caller exceeded the configured request threshold (HTTP 429)."""


class InvalidCallerCredentialError(Exception):
    """Raised when the internal reveal endpoint is called without valid
    service-to-service credentials."""
