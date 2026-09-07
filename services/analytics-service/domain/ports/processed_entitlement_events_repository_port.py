"""ProcessedEntitlementEventsRepositoryPort -- idempotency dedup ledger
for the entitlement-events consumer, keyed by `event_id` alone. One
independent ledger per independent consumer (four total: diary, profile,
nutrition_calculation, entitlement/billing) -- implementation plan
section 3, mirrors social-service's two-independent-ledgers precedent
extended to four."""

from __future__ import annotations

import uuid
from typing import Protocol


class ProcessedEntitlementEventsRepositoryPort(Protocol):
    async def is_processed(self, event_id: uuid.UUID) -> bool: ...

    async def mark_processed(self, event_id: uuid.UUID) -> None: ...
