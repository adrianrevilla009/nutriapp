"""WearableProviderPort -- the minimal, provider-agnostic shape a wearable
adapter (Apple Health, Google Fit, Fitbit, Garmin) implements
(`.claude/agents/activity-agent.md`'s domain responsibilities;
implementation plan section 1, acceptance criterion 5).

**Fitbit is the only implementation in this codebase**
(`infrastructure/external/fitbit_provider_adapter.py`), per
`/plans/activity-service/implementation-plan.md`'s "Addendum —
2026-09-11 ... Fitbit adapter (mocked, no real credentials) approved."
Apple Health, Google Fit, and Garmin remain interface-only -- no real
OAuth developer-account credentials are registered for any of the three,
and building an adapter against an unverified guess at a provider's
actual API/OAuth contract would risk shipping code that silently does the
wrong thing the moment a real credential is available. The Fitbit
adapter itself is built against Fitbit's real, publicly documented API
contract (OAuth 2.0 Authorization Code flow, Activity Logs List) but
tested entirely against fixture responses via `httpx.MockTransport` --
never a live call -- since no real Fitbit developer account exists in
this environment either (same "build against real public docs, test only
against fixtures" approach as `billing-service`'s `StripePaymentAdapter`).
This port exists so the *shape* is settled: any adapter slots in here
without touching domain or application code (ADR-0001), and the domain
layer never depends on a provider-specific SDK/API (`.claude/agents/
activity-agent.md`'s non-negotiable architectural constraint).

Every real implementation of this port MUST wrap its provider calls in a
circuit breaker, retry with backoff, and an explicit timeout (CLAUDE.md
section 2.6) -- one provider's outage must never block manual exercise
logging.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from domain.value_objects.calories_burned import CaloriesBurned
from domain.value_objects.duration_minutes import DurationMinutes
from domain.value_objects.exercise_type import ExerciseType


class WearableProviderUnavailableError(Exception):
    """Raised when a wearable provider call fails (transport error, non-2xx
    response, open circuit, or timeout) -- the caller falls back to
    surfacing sync staleness/failure to the user
    (`.claude/agents/activity-agent.md`'s rule), never a silent partial
    result."""


class WearableConnectionNotFoundError(Exception):
    """Raised when `sync`/`disconnect` is called for a user with no stored
    OAuth connection for this provider -- e.g. never connected, or already
    disconnected."""


@dataclass(frozen=True, slots=True)
class WearableSyncResult:
    """One provider-reported activity from a `sync()` call. Provider-
    agnostic shape shared by every `WearableProviderPort` implementation
    -- deliberately reuses the same value objects as a manually logged
    `ExerciseEntry` (`ExerciseType`, `DurationMinutes`, `CaloriesBurned`)
    so a future application-layer consumer can compare/dedupe the two
    without a field-by-field translation layer.

    `calories_burned` is carried through EXACTLY as the provider reports
    it -- never rounded, interpolated, or otherwise presented as more
    precise than the provider's own figure
    (`.claude/agents/activity-agent.md`'s rule).

    `label` mirrors `ExerciseEntry`'s convention: set only when
    `exercise_type` is `ExerciseType.OTHER` (an activity name the provider
    reported that doesn't map to one of this domain's enumerated types),
    display-only, never folded into the enum itself.
    """

    provider_activity_id: str
    exercise_type: ExerciseType
    duration: DurationMinutes
    calories_burned: CaloriesBurned
    started_at: datetime
    label: str | None = None


class WearableProviderPort(Protocol):
    async def connect(self, user_id: uuid.UUID, authorization_code: str) -> None:
        """Complete an OAuth connection flow for `user_id`, persisting the
        resulting tokens via the adapter's own `WearableTokenStorePort`
        (`docs/secrets-management.md` -- never logged, encrypted at rest,
        scoped per user). Raises `WearableProviderUnavailableError` on a
        transport failure, an open circuit, or a rejected grant (e.g. an
        already-used or expired `authorization_code`)."""
        ...

    async def sync(self, user_id: uuid.UUID, since: datetime) -> list[WearableSyncResult]:
        """Fetch activity data reported since `since`. Raises
        `WearableConnectionNotFoundError` if `user_id` has no stored
        connection for this provider. This method alone does NOT publish
        `WearableActivitySynced` or deduplicate against manually logged
        entries -- that is an application-layer concern
        (`.claude/agents/activity-agent.md`'s "never double-count" rule),
        not yet built; see `docs/events-catalog.md`'s `WearableActivitySynced`
        entry and `/plans/activity-service/implementation-plan.md`'s
        2026-09-11 addendum for the current scope boundary."""
        ...

    async def disconnect(self, user_id: uuid.UUID) -> None:
        """Revoke the connection immediately and stop syncing
        (`.claude/agents/activity-agent.md`'s rule: "A wearable
        disconnection/revocation must be honored immediately") -- an
        implementation MUST remove the locally stored connection
        regardless of whether the outbound revoke call to the provider
        itself succeeds, so a subsequent `sync()` call fails closed
        (`WearableConnectionNotFoundError`) rather than silently
        continuing to use a connection the user asked to remove. A no-op,
        not an error, if `user_id` has no stored connection (idempotent)."""
        ...
