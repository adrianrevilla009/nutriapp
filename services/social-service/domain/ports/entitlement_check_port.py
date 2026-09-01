"""EntitlementCheckPort -- the synchronous, circuit-breaker-guarded
fallback compensation path to `billing-service`'s
`GET /internal/v1/billing/entitlements/{user_id}`, used ONLY on an
`EntitlementCacheRepositoryPort` cache miss (implementation plan section
1.2). Concrete adapter:
`infrastructure.external.billing_entitlement_client.BillingEntitlementClient`.
Mirrors `recipe-service`'s port of the same name exactly."""

from __future__ import annotations

import uuid
from typing import Protocol


class EntitlementCheckUnavailableError(Exception):
    """Raised when billing-service's internal entitlement endpoint cannot
    be reached (circuit open, retries exhausted, timeout) or returns an
    unexpected response. Callers must fail SAFE -- treat as not entitled,
    never fail open (saga-conventions SKILL.md, ADR-0015)."""


class EntitlementCheckPort(Protocol):
    async def check_entitlement(self, user_id: uuid.UUID) -> bool: ...
