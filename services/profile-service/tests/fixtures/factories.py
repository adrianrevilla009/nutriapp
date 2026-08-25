"""In-memory fake port implementations for application-layer unit tests
(hexagonal-architecture SKILL.md: "Application: unit tests using
fake/in-memory implementations of ports, not the real adapters").
"""

from __future__ import annotations

import uuid
from datetime import datetime

from domain.events.base import DomainEvent


class FakeEventStore:
    def __init__(self) -> None:
        self._streams: dict[uuid.UUID, list[DomainEvent]] = {}

    async def append(self, event: DomainEvent) -> None:
        user_id = uuid.UUID(event.payload["user_id"])
        self._streams.setdefault(user_id, []).append(event)

    async def load(self, user_id: uuid.UUID) -> list[DomainEvent]:
        return list(self._streams.get(user_id, []))


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


class FakeSnapshotProjector:
    """Serves as both SnapshotProjectorPort (write) and
    ProfileSnapshotReadPort (read) for tests, mirroring
    PostgresSnapshotProjector's shape."""

    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, dict] = {}

    async def apply(self, event: DomainEvent) -> None:
        user_id = uuid.UUID(event.payload["user_id"])
        row = self.rows.setdefault(
            user_id,
            dict(
                user_id=user_id,
                consent_granted=False,
                weight_kg=None,
                height_cm=None,
                age=None,
                sex=None,
                activity_level=None,
                goal_type=None,
                goal_target_value=None,
                goal_target_date=None,
            ),
        )
        if event.event_type == "BiometricConsentGranted":
            row["consent_granted"] = True
        elif event.event_type == "WeightRecorded":
            row["weight_kg"] = str(event.payload["weight_kg"])
        elif event.event_type == "BodyMetricRecorded":
            column = dict(
                height="height_cm", age="age", sex="sex", activity_level="activity_level"
            ).get(event.payload["metric_type"])
            if column is not None:
                row[column] = str(event.payload["value"])
        elif event.event_type in ("GoalSet", "GoalUpdated"):
            row["goal_type"] = event.payload["goal_type"]
            target_value = event.payload.get("target_value")
            row["goal_target_value"] = str(target_value) if target_value is not None else None
            row["goal_target_date"] = event.payload.get("target_date")

    async def get_snapshot(self, user_id: uuid.UUID) -> dict | None:
        return self.rows.get(user_id)


class FakeEvolutionProjector:
    """Serves as both EvolutionProjectorPort (write) and
    EvolutionReadModelPort (read) for tests."""

    def __init__(self) -> None:
        self.entries: list[dict] = []

    async def apply(self, event: DomainEvent) -> None:
        if event.event_type == "WeightRecorded":
            metric = "weight_kg"
            value = str(event.payload["weight_kg"])
            recorded_at = event.payload["recorded_at"]
        elif event.event_type == "BodyMetricRecorded":
            metric = event.payload["metric_type"]
            value = str(event.payload["value"])
            recorded_at = event.payload["recorded_at"]
        else:
            return
        self.entries.append(
            dict(
                user_id=uuid.UUID(event.payload["user_id"]),
                metric=metric,
                value=value,
                recorded_at=datetime.fromisoformat(recorded_at),
            )
        )

    async def get_evolution(self, user_id: uuid.UUID, metric: str, from_ts, to_ts) -> list[dict]:
        results = [e for e in self.entries if e["user_id"] == user_id and e["metric"] == metric]
        if from_ts is not None:
            results = [e for e in results if e["recorded_at"] >= from_ts]
        if to_ts is not None:
            results = [e for e in results if e["recorded_at"] <= to_ts]
        return sorted(results, key=lambda e: e["recorded_at"])


class FakeDataEncryption:
    """Deterministic, reversible fake -- NOT real encryption. Prefixes the
    plaintext with the owning user_id so a cross-user decrypt attempt
    (wrong key) fails loudly, mirroring the real KMS-backed adapter's
    per-user-key isolation guarantee."""

    def __init__(self) -> None:
        self.encrypt_calls: list[tuple[uuid.UUID, str]] = []
        self.decrypt_calls: list[tuple[uuid.UUID, str]] = []

    async def encrypt(self, user_id: uuid.UUID, plaintext: str) -> str:
        self.encrypt_calls.append((user_id, plaintext))
        return f"enc:{user_id}:{plaintext}"

    async def decrypt(self, user_id: uuid.UUID, ciphertext: str) -> str:
        self.decrypt_calls.append((user_id, ciphertext))
        prefix = f"enc:{user_id}:"
        if not ciphertext.startswith(prefix):
            raise ValueError("Ciphertext was not encrypted with this user's key.")
        return ciphertext[len(prefix) :]
