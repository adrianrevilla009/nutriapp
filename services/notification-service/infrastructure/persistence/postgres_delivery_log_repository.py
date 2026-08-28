"""PostgresDeliveryLogRepository -- implements DeliveryLogRepositoryPort.
Append-only writes only (docs/notifications.md section 4)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.delivery_log_record import DeliveryLogRecord
from infrastructure.persistence.models import DeliveryLogModel


class PostgresDeliveryLogRepository:
    """Implements domain.ports.delivery_log_repository_port.DeliveryLogRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, entry: DeliveryLogRecord) -> None:
        row = DeliveryLogModel(
            delivery_id=entry.delivery_id,
            user_id=entry.user_id,
            channel=entry.channel.value,
            template_name=entry.template_id.name,
            template_version=entry.template_id.version,
            status=entry.status.value,
            attempted_at=entry.attempted_at,
            failure_reason=entry.failure_reason,
        )
        self._session.add(row)
        await self._session.flush()
