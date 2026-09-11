"""In-process fake port implementations for application-layer unit tests
(hexagonal-architecture SKILL.md: "Application: unit tests using fake/
in-memory implementations of ports, not the real adapters")."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.value_objects.retrieved_record import RetrievedRecord


class FakeProcessedEventsRepository:
    def __init__(self) -> None:
        self.processed: set[uuid.UUID] = set()
        self.mark_processed_calls: list[uuid.UUID] = []

    async def already_processed(self, event_id: uuid.UUID) -> bool:
        return event_id in self.processed

    async def mark_processed(self, event_id: uuid.UUID) -> None:
        self.processed.add(event_id)
        self.mark_processed_calls.append(event_id)


@dataclass
class _FoodEntryRow:
    entry_id: uuid.UUID
    user_id: uuid.UUID
    summary: str


class FakeDiaryHistoryRepository:
    def __init__(self) -> None:
        self.food_entries: dict[uuid.UUID, _FoodEntryRow] = {}
        self.water_intakes: dict[uuid.UUID, _FoodEntryRow] = {}
        self.upsert_food_entry_calls: list[tuple] = []
        self.upsert_water_intake_calls: list[tuple] = []
        self.recent_for_user_calls: list[uuid.UUID] = []
        self._seeded_records: dict[uuid.UUID, list[RetrievedRecord]] = {}

    def seed_records_for_user(self, user_id: uuid.UUID, records: list[RetrievedRecord]) -> None:
        self._seeded_records[user_id] = records

    async def upsert_food_entry(self, entry_id, user_id, summary, occurred_at) -> None:
        self.upsert_food_entry_calls.append((entry_id, user_id, summary, occurred_at))
        self.food_entries[entry_id] = _FoodEntryRow(entry_id, user_id, summary)

    async def remove_food_entry(self, entry_id: uuid.UUID) -> None:
        self.food_entries.pop(entry_id, None)

    async def upsert_water_intake(self, intake_id, user_id, summary, occurred_at) -> None:
        self.upsert_water_intake_calls.append((intake_id, user_id, summary, occurred_at))
        self.water_intakes[intake_id] = _FoodEntryRow(intake_id, user_id, summary)

    async def remove_water_intake(self, intake_id: uuid.UUID) -> None:
        self.water_intakes.pop(intake_id, None)

    async def recent_for_user(self, user_id: uuid.UUID, limit: int = 20) -> list[RetrievedRecord]:
        self.recent_for_user_calls.append(user_id)
        return list(self._seeded_records.get(user_id, []))


class FakeNutritionHistoryRepository:
    def __init__(self) -> None:
        self.upsert_value_calls: list[tuple] = []
        self.upsert_target_calls: list[tuple] = []
        self.recent_for_user_calls: list[uuid.UUID] = []
        self._seeded_records: dict[uuid.UUID, list[RetrievedRecord]] = {}

    def seed_records_for_user(self, user_id: uuid.UUID, records: list[RetrievedRecord]) -> None:
        self._seeded_records[user_id] = records

    async def upsert_value_recomputed(self, user_id, scope, reference_id, on_date, summary) -> None:
        self.upsert_value_calls.append((user_id, scope, reference_id, on_date, summary))

    async def upsert_target_updated(self, user_id, summary) -> None:
        self.upsert_target_calls.append((user_id, summary))

    async def recent_for_user(self, user_id: uuid.UUID, limit: int = 20) -> list[RetrievedRecord]:
        self.recent_for_user_calls.append(user_id)
        return list(self._seeded_records.get(user_id, []))


class FakeAnalyticsSignalsRepository:
    def __init__(self) -> None:
        self.upsert_calls: list[tuple] = []
        self.recent_for_user_calls: list[uuid.UUID] = []
        self._seeded_records: dict[uuid.UUID, list[RetrievedRecord]] = {}

    def seed_records_for_user(self, user_id: uuid.UUID, records: list[RetrievedRecord]) -> None:
        self._seeded_records[user_id] = records

    async def upsert_deficiency_signal(self, user_id, signal, summary, disclaimer) -> None:
        self.upsert_calls.append((user_id, signal, summary, disclaimer))

    async def recent_for_user(self, user_id: uuid.UUID, limit: int = 10) -> list[RetrievedRecord]:
        self.recent_for_user_calls.append(user_id)
        return list(self._seeded_records.get(user_id, []))


class FakeEntitlementCacheRepository:
    def __init__(self, cached: dict[uuid.UUID, bool] | None = None) -> None:
        self._cache = dict(cached or {})
        self.upsert_calls: list[tuple[uuid.UUID, bool, object]] = []

    async def get(self, user_id: uuid.UUID) -> bool | None:
        return self._cache.get(user_id)

    async def upsert(self, user_id: uuid.UUID, entitled: bool, occurred_at) -> None:
        # application/entitlement_check.py's synchronous-fallback path must
        # NEVER call this (the single most important structural invariant,
        # per the persisted test plan) -- only the billing_events_consumer
        # command handlers call it.
        self.upsert_calls.append((user_id, entitled, occurred_at))
        self._cache[user_id] = entitled


class FakeEntitlementCheckPort:
    def __init__(self, result: bool = True, raise_unavailable: bool = False) -> None:
        self._result = result
        self._raise_unavailable = raise_unavailable
        self.call_count = 0

    async def check_entitlement(self, user_id: uuid.UUID) -> bool:
        from domain.ports.entitlement_check_port import EntitlementCheckUnavailableError

        self.call_count += 1
        if self._raise_unavailable:
            raise EntitlementCheckUnavailableError("unavailable")
        return self._result


class FakeVectorStore:
    def __init__(self, hits: list | None = None, raise_unavailable: bool = False) -> None:
        self._hits = hits or []
        self._raise_unavailable = raise_unavailable
        self.search_calls: list[tuple[str, list[float], int]] = []
        self.upsert_calls: list[tuple[str, list]] = []

    async def search(self, collection: str, query_vector: list[float], top_k: int):
        from domain.ports.vector_store_port import VectorStoreUnavailableError

        self.search_calls.append((collection, query_vector, top_k))
        if self._raise_unavailable:
            raise VectorStoreUnavailableError("circuit open")
        return self._hits

    async def upsert(self, collection: str, points: list) -> None:
        self.upsert_calls.append((collection, points))

    async def exists(self, collection: str, point_id: str) -> bool:
        return False


class FakeEmbeddingPort:
    def __init__(self) -> None:
        self.embed_calls: list[str] = []

    async def embed(self, text: str) -> list[float]:
        self.embed_calls.append(text)
        return [float(len(text) % 7), 0.0, 0.0]

    @property
    def model_name(self) -> str:
        return "fake-embedding-model"

    @property
    def dimensions(self) -> int:
        return 3


class FakeConversationPort:
    def __init__(
        self, response: str = "a canned response", raise_unavailable: bool = False
    ) -> None:
        self._response = response
        self._raise_unavailable = raise_unavailable
        self.generate_calls: list[str] = []

    async def generate(self, prompt: str) -> str:
        from domain.ports.conversation_port import ConversationUnavailableError

        self.generate_calls.append(prompt)
        if self._raise_unavailable:
            raise ConversationUnavailableError("circuit open")
        return self._response


class FakeChatAuditRepository:
    def __init__(self) -> None:
        self.records: list[dict] = []

    async def record(
        self,
        user_id: uuid.UUID,
        query: str,
        retrieved_record_ids: list[str],
        prompt_template_version: str,
        had_sufficient_context: bool,
        disclaimer_included: bool,
    ) -> None:
        self.records.append(
            {
                "user_id": user_id,
                "query": query,
                "retrieved_record_ids": retrieved_record_ids,
                "prompt_template_version": prompt_template_version,
                "had_sufficient_context": had_sufficient_context,
                "disclaimer_included": disclaimer_included,
            }
        )
