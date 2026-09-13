"""WearableTokenStorePort -- persists the OAuth token pair a
`WearableProviderPort` implementation needs between separate `connect`/
`sync`/`disconnect` calls, keyed by (user_id, provider).

Deliberately its own port, not folded into `WearableProviderPort` itself
-- token persistence is a storage concern (hexagonal architecture: an
adapter should not own its own state's durability strategy), while
`WearableProviderPort` is the outbound-call concern. This split also
means a provider adapter's tests can inject a simple in-memory fake
without needing a real database, mirroring `ExerciseRepositoryPort`'s
fake in `tests/fixtures/factories.py`.

Per `.claude/agents/activity-agent.md` / `docs/secrets-management.md`:
tokens must be encrypted at rest and scoped per user. This pass ships
`infrastructure/external/in_memory_wearable_token_store.py` only (no real
credentials exist yet to protect, and the feature flag gating
`FitbitProviderAdapter` defaults to off) -- a durable, encrypted-at-rest
implementation (e.g. Postgres with envelope encryption, matching
`ADR-0023`'s per-service key ownership) is deferred to the future plan
that actually enables this in a real environment, documented in
`README.md`'s "Known limitations".
"""

from __future__ import annotations

import uuid
from typing import Protocol

from domain.value_objects.wearable_oauth_tokens import WearableOAuthTokens


class WearableTokenStorePort(Protocol):
    async def save(
        self, user_id: uuid.UUID, provider: str, tokens: WearableOAuthTokens
    ) -> None:
        """Persists (overwriting any existing record for the same
        `(user_id, provider)` pair) -- used both on initial `connect` and
        after a token refresh rotates the pair."""
        ...

    async def get(self, user_id: uuid.UUID, provider: str) -> WearableOAuthTokens | None:
        """Returns `None` if no connection exists for this
        `(user_id, provider)` pair -- never raises for "not found"."""
        ...

    async def delete(self, user_id: uuid.UUID, provider: str) -> None:
        """Idempotent -- deleting a non-existent record is a no-op, not an
        error (`WearableProviderPort.disconnect`'s idempotency
        requirement)."""
        ...
