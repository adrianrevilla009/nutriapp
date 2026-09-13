"""InMemoryWearableTokenStore -- implements WearableTokenStorePort.

Deliberately in-memory only for this pass (`domain/ports/
wearable_token_store_port.py`'s module docstring explains why: no real
Fitbit credentials exist yet, and `FitbitProviderAdapter` is gated behind
a feature flag that defaults to off -- see `infrastructure/
composition_root.py`). A durable, encrypted-at-rest implementation is
deferred to the future plan that actually enables this in a real
environment; swapping it in requires no change to `FitbitProviderAdapter`
or any domain code (ADR-0001), only a new adapter satisfying this same
port.

Process-local and non-persistent: state is lost on restart. Acceptable
today because nothing durable depends on it yet; would NOT be acceptable
once real user connections exist.
"""

from __future__ import annotations

import uuid

from domain.value_objects.wearable_oauth_tokens import WearableOAuthTokens


class InMemoryWearableTokenStore:
    """Implements domain.ports.wearable_token_store_port.WearableTokenStorePort."""

    def __init__(self) -> None:
        self._store: dict[tuple[uuid.UUID, str], WearableOAuthTokens] = {}

    async def save(self, user_id: uuid.UUID, provider: str, tokens: WearableOAuthTokens) -> None:
        self._store[(user_id, provider)] = tokens

    async def get(self, user_id: uuid.UUID, provider: str) -> WearableOAuthTokens | None:
        return self._store.get((user_id, provider))

    async def delete(self, user_id: uuid.UUID, provider: str) -> None:
        self._store.pop((user_id, provider), None)
