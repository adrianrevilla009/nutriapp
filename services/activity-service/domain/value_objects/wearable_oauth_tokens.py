"""WearableOAuthTokens -- a validated OAuth 2.0 token pair for a single
user's connection to a single wearable provider (Fitbit is the first and
only concrete consumer of this value object, see
`infrastructure/external/fitbit_provider_adapter.py`; the shape is
provider-agnostic so a future provider slots in without a new value
object).

`docs/secrets-management.md` / `.claude/agents/activity-agent.md`: OAuth
tokens must never be logged. `__repr__`/`__str__` are overridden to
redact both token values, mirroring `identity-service`'s `Password`
value object -- this is the load-bearing mechanism that keeps a stray
`logger.info(tokens)` or an uncaught exception's traceback from ever
printing a raw access/refresh token.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class InvalidWearableTokensError(ValueError):
    """Raised when an access or refresh token is empty."""


@dataclass(frozen=True, slots=True)
class WearableOAuthTokens:
    access_token: str
    refresh_token: str
    expires_at: datetime

    def __post_init__(self) -> None:
        if not self.access_token:
            raise InvalidWearableTokensError("access_token must not be empty.")
        if not self.refresh_token:
            raise InvalidWearableTokensError("refresh_token must not be empty.")

    def is_expired(self, *, now: datetime) -> bool:
        return now >= self.expires_at

    def __repr__(self) -> str:
        return "WearableOAuthTokens(***redacted***)"

    def __str__(self) -> str:
        return "***redacted***"
