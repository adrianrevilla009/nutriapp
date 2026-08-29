"""PostgresExerciseRepository -- implements ExerciseRepositoryPort.
Deliberately has no hard-delete method (matches the port's contract)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.exercise_entry import ExerciseEntry
from domain.value_objects.calories_burned import CaloriesBurned
from domain.value_objects.duration_minutes import DurationMinutes
from domain.value_objects.exercise_type import ExerciseType
from infrastructure.persistence.models import ExerciseEntryModel


def _to_domain(row: ExerciseEntryModel) -> ExerciseEntry:
    return ExerciseEntry(
        entry_id=row.entry_id,
        user_id=row.user_id,
        exercise_type=ExerciseType(row.exercise_type),
        duration=DurationMinutes(row.duration_minutes),
        calories_burned=CaloriesBurned(row.calories_burned_kcal),
        occurred_at=row.occurred_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        label=row.label,
        deleted_at=row.deleted_at,
    )


def _day_bounds_utc(occurred_on: date) -> tuple[datetime, datetime]:
    start = datetime.combine(occurred_on, time.min, tzinfo=timezone.utc)
    end = datetime.combine(occurred_on, time.max, tzinfo=timezone.utc)
    return start, end


class PostgresExerciseRepository:
    """Implements domain.ports.exercise_repository_port.ExerciseRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: ExerciseEntry) -> None:
        row = ExerciseEntryModel(
            entry_id=entry.entry_id,
            user_id=entry.user_id,
            exercise_type=entry.exercise_type.value,
            duration_minutes=int(entry.duration),
            calories_burned_kcal=float(entry.calories_burned),
            label=entry.label,
            occurred_at=entry.occurred_at,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            deleted_at=entry.deleted_at,
        )
        self._session.add(row)
        await self._session.flush()

    async def get_by_id_and_user(
        self, entry_id: uuid.UUID, user_id: uuid.UUID
    ) -> ExerciseEntry | None:
        stmt = select(ExerciseEntryModel).where(
            and_(
                ExerciseEntryModel.entry_id == entry_id,
                ExerciseEntryModel.user_id == user_id,
            )
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_domain(row) if row is not None else None

    async def update(self, entry: ExerciseEntry) -> None:
        row = await self._session.get(ExerciseEntryModel, entry.entry_id)
        if row is None:
            return
        row.exercise_type = entry.exercise_type.value
        row.duration_minutes = int(entry.duration)
        row.calories_burned_kcal = float(entry.calories_burned)
        row.label = entry.label
        row.occurred_at = entry.occurred_at
        row.updated_at = entry.updated_at
        row.deleted_at = entry.deleted_at
        await self._session.flush()

    async def list_for_user_and_date(
        self, user_id: uuid.UUID, occurred_on: date
    ) -> list[ExerciseEntry]:
        start, end = _day_bounds_utc(occurred_on)
        stmt = (
            select(ExerciseEntryModel)
            .where(
                and_(
                    ExerciseEntryModel.user_id == user_id,
                    ExerciseEntryModel.deleted_at.is_(None),
                    ExerciseEntryModel.occurred_at >= start,
                    ExerciseEntryModel.occurred_at <= end,
                )
            )
            .order_by(ExerciseEntryModel.occurred_at.asc())
        )
        result = await self._session.execute(stmt)
        return [_to_domain(row) for row in result.scalars()]
