"""PostgresEvolutionProjector -- writes AND reads profile_evolution.

One row per metric-recording event (WeightRecorded, BodyMetricRecorded);
ProfileCreated/BiometricConsentGranted/GoalSet/GoalUpdated are not
"metrics" for the evolution-graph endpoint and are ignored here. A
correction is a new WeightRecorded/BodyMetricRecorded event -> a new row,
never an UPDATE of a prior row (CLAUDE.md: never mutate historical metric
events). See PostgresSnapshotProjector's docstring for the
synchronous-projection design note.

Idempotent under replay (cqrs-event-sourcing SKILL.md's "read models must
be disposable/rebuildable by replaying events"): apply() upserts with
`ON CONFLICT (source_event_id) DO NOTHING`, keyed on the unique index
added by migrations/versions/0002_profile_evolution_source_event_id_unique.py.
Applying the same event twice (redelivery, or a rebuild replay that isn't
preceded by a truncate) is a no-op the second time, not a duplicate row or
an IntegrityError -- see scripts/rebuild_read_models.py for the actual
rebuild-from-scratch operational path (which truncates first as the
documented default, but replay is safe either way).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain.events.base import DomainEvent
from infrastructure.persistence.models import ProfileEvolutionModel

_WEIGHT_METRIC_NAME = "weight_kg"


class PostgresEvolutionProjector:
    """Implements domain.ports.evolution_projector_port.EvolutionProjectorPort
    and domain.ports.evolution_read_model_port.EvolutionReadModelPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def apply(self, event: DomainEvent) -> None:
        if event.event_type == "WeightRecorded":
            metric = _WEIGHT_METRIC_NAME
            value = str(event.payload["weight_kg"])
            recorded_at = event.payload["recorded_at"]
        elif event.event_type == "BodyMetricRecorded":
            metric = event.payload["metric_type"]
            value = str(event.payload["value"])
            recorded_at = event.payload["recorded_at"]
        else:
            return

        stmt = (
            pg_insert(ProfileEvolutionModel)
            .values(
                id=uuid.uuid4(),
                user_id=uuid.UUID(event.payload["user_id"]),
                metric=metric,
                value=value,
                recorded_at=datetime.fromisoformat(recorded_at),
                source_event_id=event.event_id,
            )
            .on_conflict_do_nothing(index_elements=["source_event_id"])
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_evolution(
        self,
        user_id: uuid.UUID,
        metric: str,
        from_ts: datetime | None,
        to_ts: datetime | None,
    ) -> list[dict[str, Any]]:
        conditions = [
            ProfileEvolutionModel.user_id == user_id,
            ProfileEvolutionModel.metric == metric,
        ]
        if from_ts is not None:
            conditions.append(ProfileEvolutionModel.recorded_at >= from_ts)
        if to_ts is not None:
            conditions.append(ProfileEvolutionModel.recorded_at <= to_ts)

        stmt = (
            select(ProfileEvolutionModel)
            .where(and_(*conditions))
            .order_by(ProfileEvolutionModel.recorded_at.asc())
        )
        result = await self._session.execute(stmt)
        return [
            {"metric": row.metric, "value": row.value, "recorded_at": row.recorded_at}
            for row in result.scalars()
        ]
