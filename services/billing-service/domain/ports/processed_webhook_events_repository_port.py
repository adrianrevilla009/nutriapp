"""ProcessedWebhookEventsRepositoryPort -- webhook idempotency boundary
(implementation plan section 1.2): dedupe by Stripe's own event `id`.
Replaying the same webhook event twice must not double-grant/double-charge
(test-plan section 1/3's mandatory idempotency cases)."""

from __future__ import annotations

from typing import Protocol


class ProcessedWebhookEventsRepositoryPort(Protocol):
    async def is_processed(self, stripe_event_id: str) -> bool: ...

    async def mark_processed(self, stripe_event_id: str) -> None: ...
