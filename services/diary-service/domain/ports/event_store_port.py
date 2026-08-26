"""EventStorePort -- generic, aggregate_type-parameterized (implementation
plan section 3/9.5: a single diary_events table, shared by one
PostgresEventStore adapter across all 4 aggregate types).

append() takes an `expected_version` (the number of events already known
to exist in the stream when the caller loaded it) so the adapter can
enforce optimistic concurrency: two concurrent writers racing to append
the next event for the same aggregate_id must not both succeed silently
-- exactly one wins, the other raises OptimisticConcurrencyError and must
reload + retry (test-plan section 2's concurrent-append case).
"""

from __future__ import annotations

from typing import Protocol

from domain.events.base import DomainEvent


class OptimisticConcurrencyError(Exception):
    """Raised when append() targets a stream position already taken by
    another writer -- the caller lost the race and must reload the
    stream and retry."""


class EventStorePort(Protocol):
    async def append(
        self, aggregate_type: str, event: DomainEvent, expected_version: int
    ) -> None: ...

    async def load(self, aggregate_type: str, aggregate_id: str) -> list[DomainEvent]: ...
