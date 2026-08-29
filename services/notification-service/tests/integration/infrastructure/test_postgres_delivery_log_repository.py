"""PostgresDeliveryLogRepository -- round-trip persistence (test-plan
section 2)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.delivery_log_record import DeliveryLogRecord
from domain.value_objects.delivery_status import DeliveryStatus
from domain.value_objects.notification_category import Channel
from domain.value_objects.template_id import TemplateId
from infrastructure.persistence.models import DeliveryLogModel
from infrastructure.persistence.postgres_delivery_log_repository import (
    PostgresDeliveryLogRepository,
)


async def test_record_persists_a_row(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresDeliveryLogRepository(session)
        delivery_id = uuid.uuid4()
        await repo.record(
            DeliveryLogRecord(
                delivery_id=delivery_id,
                user_id=uuid.uuid4(),
                channel=Channel.EMAIL,
                template_id=TemplateId("verification", 1),
                status=DeliveryStatus.SENT,
                attempted_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

        row = await session.get(DeliveryLogModel, delivery_id)
        assert row is not None
        assert row.status == "sent"
        assert row.template_name == "verification"
        assert row.template_version == 1
