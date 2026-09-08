"""Shared test fixtures/factories -- in-memory fake port implementations
(hexagonal-architecture SKILL.md: "Application: unit tests using fake/
in-memory implementations of ports, not the real adapters"). Fakes for
the write-side ports mirror the real Postgres adapters' *behavior*
(including the ledger-based reversal logic for
`correct_food_entry`/`remove_food_entry`/`remove_water_intake`) closely
enough that a handler test exercising a fake is a meaningful behavioral
test, not just a call-count check."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from domain.events.base import DomainEvent
from domain.ports.entitlement_check_port import EntitlementCheckUnavailableError
from domain.services.trend_calculator import DailyMacroTotals
from domain.value_objects.trend_point import TrendPoint

NOW = datetime(2026, 6, 8, tzinfo=timezone.utc)  # a Monday


class FakeDailyLogSummaryRepository:
    def __init__(self) -> None:
        self.days: dict[tuple[uuid.UUID, date], dict[str, float]] = {}
        self.food_contributions: dict[uuid.UUID, dict] = {}
        self.water_contributions: dict[uuid.UUID, dict] = {}
        self.apply_food_entry_calls = 0
        self.correct_food_entry_calls = 0
        self.remove_food_entry_calls = 0
        self.apply_water_intake_calls = 0
        self.remove_water_intake_calls = 0
        self.list_window_call_count = 0

    def _day(self, user_id: uuid.UUID, on_date: date) -> dict[str, float]:
        return self.days.setdefault(
            (user_id, on_date),
            {
                "calories_kcal": 0.0,
                "protein_g": 0.0,
                "carbs_g": 0.0,
                "fat_g": 0.0,
                "water_ml": 0.0,
                "entries_logged_count": 0,
            },
        )

    def _delta(
        self,
        user_id: uuid.UUID,
        on_date: date,
        *,
        calories_kcal: float = 0.0,
        protein_g: float = 0.0,
        carbs_g: float = 0.0,
        fat_g: float = 0.0,
        water_ml: float = 0.0,
        entries_logged_delta: int = 0,
    ) -> None:
        day = self._day(user_id, on_date)
        day["calories_kcal"] += calories_kcal
        day["protein_g"] += protein_g
        day["carbs_g"] += carbs_g
        day["fat_g"] += fat_g
        day["water_ml"] += water_ml
        day["entries_logged_count"] += entries_logged_delta

    async def apply_food_entry(
        self, entry_id, user_id, on_date, calories_kcal, protein_g, carbs_g, fat_g
    ) -> None:
        self.apply_food_entry_calls += 1
        if entry_id in self.food_contributions:
            return
        self.food_contributions[entry_id] = dict(
            user_id=user_id,
            on_date=on_date,
            calories_kcal=calories_kcal,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
        )
        self._delta(
            user_id,
            on_date,
            calories_kcal=calories_kcal,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            entries_logged_delta=1,
        )

    async def correct_food_entry(
        self, entry_id, user_id, on_date, calories_kcal, protein_g, carbs_g, fat_g
    ) -> None:
        self.correct_food_entry_calls += 1
        previous = self.food_contributions.get(entry_id)
        if previous is not None:
            self._delta(
                previous["user_id"],
                previous["on_date"],
                calories_kcal=-previous["calories_kcal"],
                protein_g=-previous["protein_g"],
                carbs_g=-previous["carbs_g"],
                fat_g=-previous["fat_g"],
                entries_logged_delta=-1,
            )

        self.food_contributions[entry_id] = dict(
            user_id=user_id,
            on_date=on_date,
            calories_kcal=calories_kcal,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
        )
        self._delta(
            user_id,
            on_date,
            calories_kcal=calories_kcal,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            entries_logged_delta=1,
        )

    async def remove_food_entry(self, entry_id) -> None:
        self.remove_food_entry_calls += 1
        previous = self.food_contributions.pop(entry_id, None)
        if previous is None:
            return
        self._delta(
            previous["user_id"],
            previous["on_date"],
            calories_kcal=-previous["calories_kcal"],
            protein_g=-previous["protein_g"],
            carbs_g=-previous["carbs_g"],
            fat_g=-previous["fat_g"],
            entries_logged_delta=-1,
        )

    async def apply_water_intake(self, intake_id, user_id, on_date, amount_ml) -> None:
        self.apply_water_intake_calls += 1
        if intake_id in self.water_contributions:
            return
        self.water_contributions[intake_id] = dict(
            user_id=user_id, on_date=on_date, amount_ml=amount_ml
        )
        self._delta(user_id, on_date, water_ml=amount_ml)

    async def remove_water_intake(self, intake_id) -> None:
        self.remove_water_intake_calls += 1
        previous = self.water_contributions.pop(intake_id, None)
        if previous is None:
            return
        self._delta(previous["user_id"], previous["on_date"], water_ml=-previous["amount_ml"])

    async def list_window(
        self, user_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[DailyMacroTotals]:
        self.list_window_call_count += 1
        results = []
        for (uid, on_date), totals in sorted(self.days.items(), key=lambda kv: kv[0][1]):
            if uid != user_id or not (start_date <= on_date <= end_date):
                continue
            results.append(
                DailyMacroTotals(
                    on_date=on_date,
                    calories_kcal=totals["calories_kcal"],
                    protein_g=totals["protein_g"],
                    carbs_g=totals["carbs_g"],
                    fat_g=totals["fat_g"],
                    water_ml=totals["water_ml"],
                )
            )
        return results


class FakeMicronutrientWindowRepository:
    def __init__(self) -> None:
        self.window: dict[tuple[uuid.UUID, str, date], dict] = {}
        self.current_targets: dict[tuple[uuid.UUID, str], float | None] = {}
        self.upsert_calls = 0
        self.set_current_target_min_calls = 0

    async def upsert(self, user_id, nutrient, on_date, value, target_min) -> None:
        self.upsert_calls += 1
        self.window[(user_id, nutrient, on_date)] = {"value": value, "target_min": target_min}

    async def list_recent(self, user_id, nutrient, limit_days) -> list[TrendPoint]:
        matches = [
            (on_date, row["value"])
            for (uid, nut, on_date), row in self.window.items()
            if uid == user_id and nut == nutrient
        ]
        matches.sort(key=lambda item: item[0], reverse=True)
        return [TrendPoint(on_date=d, value=v) for d, v in matches[:limit_days]]

    async def get_current_target_min(self, user_id, nutrient) -> float | None:
        return self.current_targets.get((user_id, nutrient))

    async def set_current_target_min(self, user_id, nutrient, target_min) -> None:
        self.set_current_target_min_calls += 1
        self.current_targets[(user_id, nutrient)] = target_min

    async def list_window(self, user_id, start_date, end_date) -> list[dict]:
        results = []
        for (uid, nutrient, on_date), row in sorted(self.window.items(), key=lambda kv: kv[0][2]):
            if uid != user_id or not (start_date <= on_date <= end_date):
                continue
            results.append(
                {
                    "on_date": on_date.isoformat(),
                    "nutrient": nutrient,
                    "value": row["value"],
                    "target_min": row["target_min"],
                }
            )
        return results


class FakeWeightTrendRepository:
    def __init__(self) -> None:
        self.rows: dict[tuple[uuid.UUID, date], dict] = {}
        self.upsert_calls = 0

    async def upsert(self, user_id, on_date, weight_kg_ciphertext, recorded_at) -> None:
        self.upsert_calls += 1
        self.rows[(user_id, on_date)] = {
            "weight_kg_ciphertext": weight_kg_ciphertext,
            "recorded_at": recorded_at,
        }


class FakeAnomalyAlertsRepository:
    def __init__(self) -> None:
        self.records: list[dict] = []
        self.record_detection_calls = 0

    async def most_recent_detection_at(self, user_id, signal) -> datetime | None:
        matching = [
            r["detected_at"]
            for r in self.records
            if r["user_id"] == user_id and r["signal"] == signal
        ]
        return max(matching) if matching else None

    async def record_detection(self, user_id, signal, window_days, value, detected_at) -> None:
        self.record_detection_calls += 1
        self.records.append(
            {
                "user_id": user_id,
                "signal": signal,
                "window_days": window_days,
                "value": value,
                "detected_at": detected_at,
            }
        )


class FakeEntitlementCacheRepository:
    def __init__(self, seed: dict[uuid.UUID, bool] | None = None) -> None:
        self.by_user: dict[uuid.UUID, bool] = dict(seed) if seed else {}
        self.upsert_calls = 0

    async def get(self, user_id: uuid.UUID) -> bool | None:
        return self.by_user.get(user_id)

    async def upsert(self, user_id: uuid.UUID, entitled: bool, updated_at: datetime) -> None:
        self.upsert_calls += 1
        self.by_user[user_id] = entitled


class FakeEntitlementCheckPort:
    def __init__(self, result: bool = False, raise_unavailable: bool = False) -> None:
        self.result = result
        self.raise_unavailable = raise_unavailable
        self.calls: list[uuid.UUID] = []

    async def check_entitlement(self, user_id: uuid.UUID) -> bool:
        self.calls.append(user_id)
        if self.raise_unavailable:
            raise EntitlementCheckUnavailableError("billing-service unavailable (fake).")
        return self.result


class FakeExportAuditRepository:
    def __init__(self) -> None:
        self.records: list[dict] = []

    async def record(
        self,
        user_id,
        report_type,
        requested_at,
        export_format,
        start_date,
        end_date,
        row_count,
        outcome,
        actor_id,
        action,
        target_type,
        target_id,
        correlation_id,
        rejection_reason=None,
    ) -> None:
        self.records.append(
            dict(
                user_id=user_id,
                report_type=report_type,
                requested_at=requested_at,
                export_format=export_format,
                start_date=start_date,
                end_date=end_date,
                row_count=row_count,
                outcome=outcome,
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                correlation_id=correlation_id,
                rejection_reason=rejection_reason,
            )
        )


class FakeOutboxRepository:
    def __init__(self) -> None:
        self.enqueued: list[DomainEvent] = []
        self.published_ids: set[uuid.UUID] = set()

    async def enqueue(self, event: DomainEvent) -> None:
        self.enqueued.append(event)

    async def fetch_unpublished(self, limit: int = 100) -> list[DomainEvent]:
        pending = [e for e in self.enqueued if e.event_id not in self.published_ids]
        return pending[:limit]

    async def mark_published(self, event_id: uuid.UUID) -> None:
        self.published_ids.add(event_id)


class _FakeEventIdLedger:
    """Shared in-memory idempotency ledger backing all four
    Processed*EventsRepositoryPort fakes -- structurally identical
    (`is_processed`/`mark_processed` keyed by `event_id` alone), same
    "one fake, several aliases" convention social-service's own
    factories.py uses."""

    def __init__(self) -> None:
        self.processed: set[uuid.UUID] = set()

    async def is_processed(self, event_id: uuid.UUID) -> bool:
        return event_id in self.processed

    async def mark_processed(self, event_id: uuid.UUID) -> None:
        self.processed.add(event_id)


FakeProcessedDiaryEventsRepository = _FakeEventIdLedger
FakeProcessedProfileEventsRepository = _FakeEventIdLedger
FakeProcessedNutritionCalculationEventsRepository = _FakeEventIdLedger
FakeProcessedEntitlementEventsRepository = _FakeEventIdLedger
