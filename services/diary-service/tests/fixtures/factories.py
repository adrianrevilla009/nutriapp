"""In-memory fake port implementations for application-layer unit tests
(hexagonal-architecture SKILL.md: "Application: unit tests using
fake/in-memory implementations of ports, not the real adapters").
"""

from __future__ import annotations

import uuid
from datetime import date

from domain.events.base import DomainEvent
from domain.ports.event_store_port import OptimisticConcurrencyError


class FakeEventStore:
    """Fake EventStorePort -- aggregate_type-parameterized, enforces the
    same optimistic-concurrency contract as PostgresEventStore (expected
    the caller's `expected_version` to equal the stream's current length)."""

    def __init__(self) -> None:
        self._streams: dict[tuple[str, str], list[DomainEvent]] = {}

    async def append(self, aggregate_type: str, event: DomainEvent, expected_version: int) -> None:
        key = (aggregate_type, event.aggregate_id)
        stream = self._streams.setdefault(key, [])
        if len(stream) != expected_version:
            raise OptimisticConcurrencyError(
                f"Expected version {expected_version} but stream is at {len(stream)}."
            )
        stream.append(event)

    async def load(self, aggregate_type: str, aggregate_id: str) -> list[DomainEvent]:
        return list(self._streams.get((aggregate_type, aggregate_id), []))


class FakeOutboxRepository:
    def __init__(self) -> None:
        self.enqueued: list[DomainEvent] = []
        self.published_ids: set[uuid.UUID] = set()

    async def enqueue(self, event: DomainEvent) -> None:
        self.enqueued.append(event)

    async def fetch_unpublished(self, limit: int = 100) -> list[DomainEvent]:
        return [e for e in self.enqueued if e.event_id not in self.published_ids][:limit]

    async def mark_published(self, event_id: uuid.UUID) -> None:
        self.published_ids.add(event_id)


class FakeProcessedEventsRepository:
    def __init__(self) -> None:
        self._processed: set[uuid.UUID] = set()

    async def already_processed(self, event_id: uuid.UUID) -> bool:
        return event_id in self._processed

    async def mark_processed(self, event_id: uuid.UUID) -> None:
        self._processed.add(event_id)


class FakeDailySummaryReadPort:
    def __init__(self) -> None:
        self.rows: dict[tuple[uuid.UUID, date], dict] = {}

    async def get_summary(self, user_id: uuid.UUID, summary_date: date) -> dict | None:
        return self.rows.get((user_id, summary_date))


class FakeDailySummaryCachePort:
    def __init__(self) -> None:
        self.cache: dict[tuple[uuid.UUID, date], dict] = {}
        self.get_calls: list[tuple[uuid.UUID, date]] = []
        self.set_calls: list[tuple[uuid.UUID, date]] = []
        self.invalidate_calls: list[tuple[uuid.UUID, date]] = []

    async def get(self, user_id: uuid.UUID, summary_date: date) -> dict | None:
        self.get_calls.append((user_id, summary_date))
        return self.cache.get((user_id, summary_date))

    async def set(self, user_id: uuid.UUID, summary_date: date, summary: dict) -> None:
        self.set_calls.append((user_id, summary_date))
        self.cache[(user_id, summary_date)] = summary

    async def invalidate(self, user_id: uuid.UUID, summary_date: date) -> None:
        self.invalidate_calls.append((user_id, summary_date))
        self.cache.pop((user_id, summary_date), None)


class FakeFoodEntriesReadPort:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    async def list_entries(self, user_id: uuid.UUID, from_date, to_date) -> list[dict]:
        return [row for row in self.rows if row["user_id"] == user_id]


class FakeWaterIntakeReadPort:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    async def list_intake(self, user_id: uuid.UUID, from_date, to_date) -> list[dict]:
        return [row for row in self.rows if row["user_id"] == user_id]


class FakeFastingWindowsReadPort:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    async def get_history(self, user_id: uuid.UUID, limit: int = 50) -> list[dict]:
        return [row for row in self.rows if row["user_id"] == user_id][:limit]


class FakeMealPlanReadPort:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    async def get_calendar(self, user_id: uuid.UUID, from_date, to_date) -> list[dict]:
        return [row for row in self.rows if row["user_id"] == user_id]
