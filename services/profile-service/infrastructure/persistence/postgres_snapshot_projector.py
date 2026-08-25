"""PostgresSnapshotProjector -- writes AND reads profile_snapshot.

Implements both the write side (SnapshotProjectorPort.apply, called
synchronously by command handlers right after the event-store append +
outbox enqueue, in the same unit of work/session -- see profile-service's
README "Projection consistency" note for why this deviates from a
separate async RabbitMQ-subscribing projector process) and the read side
(ProfileSnapshotReadPort.get_snapshot, used by
application/queries/get_profile_snapshot.py). Fully disposable: replaying
the whole profile_events stream through `apply()` in order reproduces this
table exactly (cqrs-event-sourcing SKILL.md) -- proven by the
projector-replay integration test.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from domain.events.base import DomainEvent
from infrastructure.persistence.models import ProfileSnapshotModel

_METRIC_TYPE_TO_COLUMN = {
    "height": "height_cm",
    "age": "age",
    "sex": "sex",
    "activity_level": "activity_level",
}


class PostgresSnapshotProjector:
    """Implements domain.ports.snapshot_projector_port.SnapshotProjectorPort
    and domain.ports.profile_snapshot_read_port.ProfileSnapshotReadPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _get_or_create_row(self, user_id: uuid.UUID, occurred_at) -> ProfileSnapshotModel:
        row = await self._session.get(ProfileSnapshotModel, user_id)
        if row is None:
            row = ProfileSnapshotModel(
                user_id=user_id, consent_granted=False, updated_at=occurred_at
            )
            self._session.add(row)
        return row

    async def apply(self, event: DomainEvent) -> None:
        user_id = uuid.UUID(event.payload["user_id"])
        row = await self._get_or_create_row(user_id, event.occurred_at)
        row.updated_at = event.occurred_at

        if event.event_type == "BiometricConsentGranted":
            row.consent_granted = True
        elif event.event_type == "WeightRecorded":
            row.weight_kg = str(event.payload["weight_kg"])
        elif event.event_type == "BodyMetricRecorded":
            column = _METRIC_TYPE_TO_COLUMN.get(event.payload["metric_type"])
            if column is not None:
                setattr(row, column, str(event.payload["value"]))
        elif event.event_type in ("GoalSet", "GoalUpdated"):
            row.goal_type = event.payload["goal_type"]
            target_value = event.payload.get("target_value")
            row.goal_target_value = str(target_value) if target_value is not None else None
            target_date = event.payload.get("target_date")
            row.goal_target_date = date.fromisoformat(target_date) if target_date else None

        await self._session.flush()

    async def get_snapshot(self, user_id: uuid.UUID) -> dict[str, Any] | None:
        row = await self._session.get(ProfileSnapshotModel, user_id)
        if row is None:
            return None
        return {
            "user_id": row.user_id,
            "consent_granted": row.consent_granted,
            "weight_kg": row.weight_kg,
            "height_cm": row.height_cm,
            "age": row.age,
            "sex": row.sex,
            "activity_level": row.activity_level,
            "goal_type": row.goal_type,
            "goal_target_value": row.goal_target_value,
            "goal_target_date": row.goal_target_date.isoformat() if row.goal_target_date else None,
        }
