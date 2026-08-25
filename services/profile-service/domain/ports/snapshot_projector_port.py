from __future__ import annotations

from typing import Protocol

from domain.events.base import DomainEvent


class SnapshotProjectorPort(Protocol):
    """Write-side of the profile_snapshot read model -- applied
    synchronously by command handlers, in the same unit of work as the
    event-store append, right after the outbox enqueue (implementation
    plan Addendum, see profile-service README's "Projection consistency"
    note). Always disposable/rebuildable by replaying the full event
    stream through the same `apply` method."""

    async def apply(self, event: DomainEvent) -> None: ...
