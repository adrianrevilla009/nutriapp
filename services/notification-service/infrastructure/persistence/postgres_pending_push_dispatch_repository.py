"""PostgresPendingPushDispatchRepository -- implements
PendingPushDispatchRepositoryPort."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.pending_push_dispatch import PendingPushDispatch
from domain.value_objects.notification_category import NotificationCategory
from domain.value_objects.pending_dispatch_status import PendingDispatchStatus
from domain.value_objects.template_id import TemplateId
from infrastructure.persistence.models import PendingPushDispatchModel


def _to_entity(row: PendingPushDispatchModel) -> PendingPushDispatch:
    return PendingPushDispatch(
        dispatch_id=row.dispatch_id,
        user_id=row.user_id,
        category=NotificationCategory.push(row.category),
        template_id=TemplateId(row.template_name, row.template_version),
        context=dict(row.context),
        correlation_id=row.correlation_id,
        earliest_dispatch_at=row.earliest_dispatch_at,
        status=PendingDispatchStatus(row.status),
    )


class PostgresPendingPushDispatchRepository:
    """Implements
    domain.ports.pending_push_dispatch_repository_port.PendingPushDispatchRepositoryPort.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, dispatch: PendingPushDispatch) -> None:
        self._session.add(
            PendingPushDispatchModel(
                dispatch_id=dispatch.dispatch_id,
                user_id=dispatch.user_id,
                category=dispatch.category.name,
                template_name=dispatch.template_id.name,
                template_version=dispatch.template_id.version,
                context=dispatch.context,
                correlation_id=dispatch.correlation_id,
                earliest_dispatch_at=dispatch.earliest_dispatch_at,
                status=dispatch.status.value,
            )
        )
        await self._session.flush()

    async def list_due(self, now: datetime) -> list[PendingPushDispatch]:
        result = await self._session.execute(
            select(PendingPushDispatchModel).where(
                PendingPushDispatchModel.status == PendingDispatchStatus.PENDING.value,
                PendingPushDispatchModel.earliest_dispatch_at <= now,
            )
        )
        return [_to_entity(row) for row in result.scalars()]

    async def mark_status(
        self,
        dispatch_id: uuid.UUID,
        status: PendingDispatchStatus,
        earliest_dispatch_at: datetime | None = None,
    ) -> None:
        values: dict[str, object] = {"status": status.value}
        if earliest_dispatch_at is not None:
            values["earliest_dispatch_at"] = earliest_dispatch_at
        await self._session.execute(
            update(PendingPushDispatchModel)
            .where(PendingPushDispatchModel.dispatch_id == dispatch_id)
            .values(**values)
        )
        await self._session.flush()
