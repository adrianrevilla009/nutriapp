from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.fasting_window import FastingWindow
from infrastructure.persistence.projectors.fasting_windows_projector import (
    PostgresFastingWindowsProjector,
)

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


@pytest.fixture()
async def session(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as s:
        yield s


async def test_replaying_fixed_event_sequence_produces_expected_rows(session):
    user_id = uuid.uuid4()
    aggregate = FastingWindow.rebuild(user_id, [])
    w1, w2 = uuid.uuid4(), uuid.uuid4()
    started_1 = aggregate.start_window(w1, NOW, "corr-1")
    ended_1 = aggregate.end_window(w1, NOW + timedelta(hours=16), "corr-2")
    rebuilt = FastingWindow.rebuild(user_id, [started_1, ended_1])
    started_2 = rebuilt.start_window(w2, NOW + timedelta(hours=20), "corr-3")

    projector = PostgresFastingWindowsProjector(session)
    for event in [started_1, ended_1, started_2]:
        await projector.apply(event)
    await session.commit()

    history = await projector.get_history(user_id)
    by_id = {row["window_id"]: row for row in history}
    assert by_id[w1]["ended_at"] is not None
    assert by_id[w2]["ended_at"] is None

    ended_count = await projector.count_ended_on(user_id, (NOW + timedelta(hours=16)).date())
    assert ended_count == 1
