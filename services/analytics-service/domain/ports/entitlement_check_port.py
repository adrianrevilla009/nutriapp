"""EntitlementCheckPort -- synchronous, circuit-breaker-guarded fallback to
billing-service's `GET /internal/v1/billing/entitlements/{user_id}`,
reached only on an `EntitlementCacheRepositoryPort` cache miss. Concrete
adapter: `infrastructure.external.billing_entitlement_client.BillingEntitlementClient`.
Mirrors `recipe-service`'s/`social-service`'s port of the same name."""

from __future__ import annotations

import uuid
from typing import Protocol


class EntitlementCheckUnavailableError(Exception):
    """Callers must fail SAFE -- treat as not entitled, never fail open
    (saga-conventions SKILL.md, ADR-0015)."""


class EntitlementCheckPort(Protocol):
    async def check_entitlement(self, user_id: uuid.UUID) -> bool: ...
