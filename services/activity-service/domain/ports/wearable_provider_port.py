"""WearableProviderPort -- the minimal, provider-agnostic shape a future
wearable adapter (Apple Health, Google Fit, Fitbit, Garmin) will
implement (`.claude/agents/activity-agent.md`'s domain responsibilities;
implementation plan section 1, acceptance criterion 5).

**Interface only. Zero implementations in this codebase.** No real OAuth
developer-account credentials are registered for any of the four
providers (implementation plan section 1's explicit MVP scope decision) --
building an adapter against an unverified guess at any provider's actual
API/OAuth contract would risk shipping code that silently does the wrong
thing the moment a real credential is available, and no fixture in this
repository simulates a real provider response for the same reason. This
port exists so the *shape* is settled now: a future adapter slots in here
without touching domain or application code (ADR-0001), and the domain
layer never depends on a provider-specific SDK/API (`.claude/agents/
activity-agent.md`'s non-negotiable architectural constraint).

Every real implementation of this port MUST wrap its provider calls in a
circuit breaker, retry with backoff, and an explicit timeout (CLAUDE.md
section 2.6) -- one provider's outage must never block manual exercise
logging, which this port's absence of any implementation trivially
guarantees today.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol


class WearableSyncResult:
    """Placeholder return shape for a future `sync()` implementation --
    intentionally not fleshed out further than this: a real provider's
    actual response shape is unknown until a developer account exists and
    the contract can be verified against it, not guessed at."""


class WearableProviderPort(Protocol):
    async def connect(self, user_id: uuid.UUID, authorization_code: str) -> None:
        """Complete an OAuth connection flow for `user_id`. OAuth tokens
        must be handled per `docs/secrets-management.md` -- never logged,
        encrypted at rest, scoped per user -- by whatever concrete adapter
        eventually implements this."""
        ...

    async def sync(self, user_id: uuid.UUID, since: datetime) -> list[WearableSyncResult]:
        """Fetch activity data reported since `since`. A real
        implementation publishes `WearableActivitySynced` (documented as
        planned, not yet existing, in docs/events-catalog.md) and must
        deduplicate against manually logged entries for the same time
        window -- never double-count (`.claude/agents/activity-agent.md`'s
        rule) -- once this is actually built."""
        ...

    async def disconnect(self, user_id: uuid.UUID) -> None:
        """Revoke the connection immediately and stop syncing
        (`.claude/agents/activity-agent.md`'s rule: "A wearable
        disconnection/revocation must be honored immediately"). A real
        implementation also offers clear deletion of previously-synced
        data on request."""
        ...
