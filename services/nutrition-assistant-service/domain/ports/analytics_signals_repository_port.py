"""AnalyticsSignalsRepositoryPort -- structured projection of
analytics-service's NutrientDeficiencyDetected events. The `disclaimer`
field is stored and surfaced verbatim, never re-worded by this service
(implementation plan section 5). Concrete adapter:
infrastructure.persistence.postgres_analytics_signals_repository.PostgresAnalyticsSignalsRepository."""

from __future__ import annotations

import uuid
from typing import Protocol

from domain.value_objects.retrieved_record import RetrievedRecord


class AnalyticsSignalsRepositoryPort(Protocol):
    async def upsert_deficiency_signal(
        self,
        user_id: uuid.UUID,
        signal: str,
        summary: str,
        disclaimer: str,
    ) -> None: ...

    async def recent_for_user(
        self, user_id: uuid.UUID, limit: int = 10
    ) -> list[RetrievedRecord]: ...
