"""In-memory fake port implementations for application-layer unit tests
(never a real DB/broker/HTTP call at this layer -- testing-strategy
SKILL.md)."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import date, datetime, timezone

from domain.entities.daily_nutrition_total import DailyNutritionTotal
from domain.entities.nutrition_target import NutritionTarget
from domain.events.base import DomainEvent
from domain.ports.profile_reveal_port import ProfileRevealUnavailableError, RevealedMetrics
from domain.ports.user_metrics_snapshot_port import UserMetricsSnapshotMetadata
from domain.value_objects.activity_level import ActivityLevel
from domain.value_objects.goal_type import GoalType
from domain.value_objects.nutrient_total_line import NutrientTotalLine
from domain.value_objects.sex import Sex


class FakeCurrentTargetCache:
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, NutritionTarget] = {}
        self.get_calls = 0
        self.set_calls = 0

    async def get(self, user_id: uuid.UUID) -> NutritionTarget | None:
        self.get_calls += 1
        return self._store.get(user_id)

    async def set(self, user_id: uuid.UUID, target: NutritionTarget) -> None:
        self.set_calls += 1
        self._store[user_id] = target

    async def invalidate(self, user_id: uuid.UUID) -> None:
        self._store.pop(user_id, None)


class FakeCurrentTotalCache:
    def __init__(self) -> None:
        self._store: dict[tuple[uuid.UUID, date], NutrientTotalLine] = {}
        self.get_calls = 0
        self.set_calls = 0

    async def get(self, user_id: uuid.UUID, total_date: date) -> NutrientTotalLine | None:
        self.get_calls += 1
        return self._store.get((user_id, total_date))

    async def set(self, user_id: uuid.UUID, total_date: date, line: NutrientTotalLine) -> None:
        self.set_calls += 1
        self._store[(user_id, total_date)] = line

    async def invalidate(self, user_id: uuid.UUID, total_date: date) -> None:
        self._store.pop((user_id, total_date), None)


class FakeDailyNutritionTotalRepository:
    def __init__(self) -> None:
        self._store: dict[tuple[uuid.UUID, date], DailyNutritionTotal] = {}

    async def get(self, user_id: uuid.UUID, total_date: date) -> DailyNutritionTotal | None:
        return self._store.get((user_id, total_date))

    async def upsert(self, total: DailyNutritionTotal) -> None:
        self._store[(total.user_id, total.total_date)] = total

    async def find_date_for_entry(self, user_id: uuid.UUID, entry_id: uuid.UUID) -> date | None:
        for (stored_user_id, stored_date), total in self._store.items():
            if stored_user_id == user_id and entry_id in total.entries:
                return stored_date
        return None


class FakeNutrientPanelMirrorRepository:
    def __init__(self) -> None:
        self._store: dict[str, Mapping[str, float | None]] = {}

    async def get_by_reference_id(
        self, source_reference_id: str
    ) -> Mapping[str, float | None] | None:
        return self._store.get(source_reference_id)

    async def upsert(self, source_reference_id: str, panel: Mapping[str, float | None]) -> None:
        self._store[source_reference_id] = dict(panel)


class FakeNutritionTargetRepository:
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, NutritionTarget] = {}

    async def get_current(self, user_id: uuid.UUID) -> NutritionTarget | None:
        return self._store.get(user_id)

    async def upsert(self, target: NutritionTarget) -> None:
        self._store[target.user_id] = target


class FakeTargetHistoryRepository:
    def __init__(self) -> None:
        self.appended: list[NutritionTarget] = []

    async def append(self, target: NutritionTarget) -> None:
        self.appended.append(target)

    async def list_history(self, user_id: uuid.UUID) -> list[NutritionTarget]:
        return [target for target in self.appended if target.user_id == user_id]


class FakeUserMetricsSnapshotRepository:
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, UserMetricsSnapshotMetadata] = {}

    async def record_fetch(self, metadata: UserMetricsSnapshotMetadata) -> None:
        self._store[metadata.user_id] = metadata

    async def get(self, user_id: uuid.UUID) -> UserMetricsSnapshotMetadata | None:
        return self._store.get(user_id)


class FakeOutboxRepository:
    def __init__(self) -> None:
        self.enqueued: list[DomainEvent] = []

    async def enqueue(self, event: DomainEvent) -> None:
        self.enqueued.append(event)

    async def fetch_unpublished(self, limit: int = 100) -> list[DomainEvent]:
        return list(self.enqueued[:limit])

    async def mark_published(self, event_id: uuid.UUID) -> None:
        pass


class FakeProfileRevealPort:
    """Configurable fake: either returns a fixed `RevealedMetrics` or
    raises `ProfileRevealUnavailableError`, and counts calls (test-plan
    section 2's idempotency assertion: "asserted via a fake
    ProfileRevealPort call-count, not two")."""

    def __init__(
        self,
        metrics: RevealedMetrics | None = None,
        should_fail: bool = False,
    ) -> None:
        self._metrics = metrics or default_revealed_metrics()
        self._should_fail = should_fail
        self.call_count = 0

    async def reveal(self, user_id: uuid.UUID) -> RevealedMetrics:
        self.call_count += 1
        if self._should_fail:
            raise ProfileRevealUnavailableError("fake profile-service reveal failure")
        return self._metrics


class FakeProcessedEventsRepository:
    def __init__(self) -> None:
        self._store: set[tuple[str, uuid.UUID]] = set()

    async def already_processed(self, consumer_name: str, event_id: uuid.UUID) -> bool:
        return (consumer_name, event_id) in self._store

    async def mark_processed(self, consumer_name: str, event_id: uuid.UUID) -> None:
        self._store.add((consumer_name, event_id))


def default_revealed_metrics(**overrides: object) -> RevealedMetrics:
    defaults: dict[str, object] = {
        "weight_kg": 70.0,
        "height_cm": 175.0,
        "age": 25,
        "sex": Sex.MALE,
        "activity_level": ActivityLevel.MODERATE,
        "goal_type": GoalType.MAINTAIN,
    }
    defaults.update(overrides)
    return RevealedMetrics(**defaults)  # type: ignore[arg-type]


def make_food_entry_logged_payload(
    *,
    entry_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    quantity: float = 150.0,
    source_type: str = "catalog_product",
    source_reference_id: str = "product-1",
    occurred_at: datetime | None = None,
) -> dict:
    return {
        "entry_id": str(entry_id or uuid.uuid4()),
        "user_id": str(user_id or uuid.uuid4()),
        "source": {
            "source_type": source_type,
            "source_reference_id": source_reference_id,
            "snapshot": {
                "name": "Test Product",
                "brand": None,
                "quantity": quantity,
                "unit": "g",
                "macros_per_unit": {
                    "calories_kcal": 200.0,
                    "protein_g": 10.0,
                    "carbs_g": 20.0,
                    "fat_g": 5.0,
                },
            },
        },
        "meal_slot": "lunch",
        "occurred_at": (occurred_at or datetime.now(timezone.utc)).isoformat(),
        "planned_from_entry_id": None,
    }


def wrap_event(
    event_type: str, payload: dict, *, version: int = 1, correlation_id: str = "corr-1"
) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "aggregate_id": payload.get("entry_id") or payload.get("user_id"),
        "event_type": event_type,
        "version": version,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
        "metadata": {
            "correlation_id": correlation_id,
            "causation_id": None,
            "user_id": payload.get("user_id"),
        },
    }
