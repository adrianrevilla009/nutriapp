from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.water_intake_entry import WaterIntakeEntry
from domain.value_objects.water_amount_ml import WaterAmountMl
from infrastructure.persistence.projectors.water_intake_projector import (
    PostgresWaterIntakeProjector,
)

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


@pytest.fixture
async def session(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as s:
        yield s


async def test_replaying_fixed_event_sequence_produces_expected_row(session):
    intake_id = uuid.uuid4()
    user_id = uuid.uuid4()
    entry, logged = WaterIntakeEntry.log(
        intake_id=intake_id,
        user_id=user_id,
        amount=WaterAmountMl(250.0),
        occurred_at=NOW,
        correlation_id="corr-1",
    )
    removed = entry.remove(removed_at=NOW, correlation_id="corr-2")

    projector = PostgresWaterIntakeProjector(session)
    await projector.apply(logged)
    await projector.apply(removed)
    await session.commit()

    rows = await projector.list_intake(user_id, None, None)
    assert len(rows) == 1
    assert rows[0]["amount_ml"] == 250.0
    assert rows[0]["removed"] is True
