"""Application-layer error types."""

from __future__ import annotations


class ProfileNotFoundError(Exception):
    """Raised when a query/command targets a user_id with no profile yet."""


class InvalidCallerCredentialError(Exception):
    """Raised when the internal reveal-metrics endpoint's caller-presented
    credential doesn't match any configured per-caller credential
    (implementation plan Addendum 2, requirement 3). Maps to 401."""


class RevealRateLimitedError(Exception):
    """Raised when the caller-credential + user_id combination has
    exceeded the reveal-metrics endpoint's configured rate limit
    (implementation plan Addendum 2, requirement 4). Maps to 429."""
