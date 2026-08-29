"""TokenRevealPort -- the synchronous, circuit-breaker-guarded call into
identity-service's existing internal endpoint
(POST /internal/v1/auth/tokens/{reference_id}/reveal, implementation plan
section 1/6). This is a deliberate, single-endpoint exception to
notification-service being otherwise a pure event consumer
(docs/domain-glossary-and-context-map.md)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


class TokenRevealUnavailableError(Exception):
    """Raised when the reveal call fails, times out, or the circuit is open."""


class TokenRevealNotFoundError(Exception):
    """Raised when identity-service reports the reference id is unknown --
    mapped explicitly, never surfaced as an unhandled exception."""


@dataclass(frozen=True, slots=True)
class RevealedToken:
    secret: str
    user_id: uuid.UUID
    kind: str


class TokenRevealPort(Protocol):
    async def reveal(self, reference_id: str) -> RevealedToken: ...
