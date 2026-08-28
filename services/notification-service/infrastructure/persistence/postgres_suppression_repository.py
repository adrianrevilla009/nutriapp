"""PostgresSuppressionRepository -- implements SuppressionRepositoryPort.
The permanent suppression list (docs/notifications.md section 4) -- `add`
is idempotent (upsert), never removed by this repository; re-addition to
the allowed set requires a separate, explicit-consent code path."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain.value_objects.notification_category import Channel
from domain.value_objects.suppression_reason import SuppressionReason
from infrastructure.persistence.models import SuppressionListModel


class PostgresSuppressionRepository:
    """Implements domain.ports.suppression_repository_port.SuppressionRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_suppressed(
        self, user_id: uuid.UUID, channel: Channel, address_or_device: str
    ) -> bool:
        result = await self._session.execute(
            select(SuppressionListModel).where(
                SuppressionListModel.user_id == user_id,
                SuppressionListModel.channel == channel.value,
                SuppressionListModel.address_or_device == address_or_device,
            )
        )
        return result.scalar_one_or_none() is not None

    async def add(
        self,
        user_id: uuid.UUID,
        channel: Channel,
        address_or_device: str,
        reason: SuppressionReason,
    ) -> None:
        stmt = insert(SuppressionListModel).values(
            user_id=user_id,
            channel=channel.value,
            address_or_device=address_or_device,
            reason=reason.value,
            suppressed_at=datetime.now(timezone.utc),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "channel", "address_or_device"],
            set_={"reason": reason.value},
        )
        await self._session.execute(stmt)
        await self._session.flush()
