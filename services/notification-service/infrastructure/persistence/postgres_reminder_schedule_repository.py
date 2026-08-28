"""PostgresReminderScheduleRepository -- implements
ReminderScheduleRepositoryPort. `upsert` is keyed by the unique
(source_aggregate_id, category) constraint (migration 0001) so a
MealPlanUpdated re-application updates the existing row in place, never
duplicates it (test-plan section 1)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.reminder_schedule_entry import ReminderScheduleEntry
from domain.value_objects.notification_category import NotificationCategory
from domain.value_objects.reminder_status import ReminderStatus
from infrastructure.persistence.models import ReminderScheduleModel


def _to_entity(row: ReminderScheduleModel) -> ReminderScheduleEntry:
    return ReminderScheduleEntry(
        schedule_id=row.schedule_id,
        user_id=row.user_id,
        category=NotificationCategory.push(row.category),
        source_aggregate_id=row.source_aggregate_id,
        due_at=row.due_at,
        relevance_expires_at=row.relevance_expires_at,
        status=ReminderStatus(row.status),
        next_eligible_check_at=row.next_eligible_check_at,
    )


class PostgresReminderScheduleRepository:
    """Implements domain.ports.reminder_schedule_repository_port.ReminderScheduleRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, entry: ReminderScheduleEntry) -> None:
        stmt = insert(ReminderScheduleModel).values(
            schedule_id=entry.schedule_id,
            user_id=entry.user_id,
            category=entry.category.name,
            source_aggregate_id=entry.source_aggregate_id,
            due_at=entry.due_at,
            relevance_expires_at=entry.relevance_expires_at,
            status=entry.status.value,
            next_eligible_check_at=entry.next_eligible_check_at,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_reminder_schedule_source_category",
            set_={
                "user_id": entry.user_id,
                "due_at": entry.due_at,
                "relevance_expires_at": entry.relevance_expires_at,
                "status": entry.status.value,
                "next_eligible_check_at": entry.next_eligible_check_at,
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_by_source(
        self, source_aggregate_id: str, category_name: str
    ) -> ReminderScheduleEntry | None:
        result = await self._session.execute(
            select(ReminderScheduleModel).where(
                ReminderScheduleModel.source_aggregate_id == source_aggregate_id,
                ReminderScheduleModel.category == category_name,
            )
        )
        row = result.scalar_one_or_none()
        return None if row is None else _to_entity(row)

    async def remove_by_source(self, source_aggregate_id: str, category_name: str) -> None:
        result = await self._session.execute(
            select(ReminderScheduleModel).where(
                ReminderScheduleModel.source_aggregate_id == source_aggregate_id,
                ReminderScheduleModel.category == category_name,
            )
        )
        row = result.scalar_one_or_none()
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()

    async def list_pending(self, now: datetime) -> list[ReminderScheduleEntry]:
        result = await self._session.execute(
            select(ReminderScheduleModel).where(
                ReminderScheduleModel.status == ReminderStatus.PENDING.value,
                or_(
                    ReminderScheduleModel.next_eligible_check_at.is_(None),
                    ReminderScheduleModel.next_eligible_check_at <= now,
                ),
            )
        )
        return [_to_entity(row) for row in result.scalars()]

    async def mark_status(
        self,
        schedule_id: uuid.UUID,
        status: ReminderStatus,
        next_eligible_check_at: datetime | None = None,
    ) -> None:
        await self._session.execute(
            update(ReminderScheduleModel)
            .where(ReminderScheduleModel.schedule_id == schedule_id)
            .values(status=status.value, next_eligible_check_at=next_eligible_check_at)
        )
        await self._session.flush()
