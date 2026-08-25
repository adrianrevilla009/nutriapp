from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from application.queries.get_evolution_timeline import (
    GetEvolutionTimelineHandler,
    GetEvolutionTimelineQuery,
)
from tests.fixtures.factories import FakeDataEncryption, FakeEvolutionProjector


async def test_returns_entries_filtered_by_metric_and_window_ordered():
    evolution = FakeEvolutionProjector()
    encryption = FakeDataEncryption()
    user_id = uuid.uuid4()
    base = datetime(2026, 8, 1, tzinfo=timezone.utc)
    evolution.entries = [
        dict(
            user_id=user_id,
            metric="weight_kg",
            value=await encryption.encrypt(user_id, "70.0"),
            recorded_at=base,
        ),
        dict(
            user_id=user_id,
            metric="weight_kg",
            value=await encryption.encrypt(user_id, "68.0"),
            recorded_at=base + timedelta(days=10),
        ),
        dict(
            user_id=user_id,
            metric="height",
            value=await encryption.encrypt(user_id, "175.0"),
            recorded_at=base,
        ),
    ]

    handler = GetEvolutionTimelineHandler(evolution, encryption)
    entries = await handler.handle(GetEvolutionTimelineQuery(user_id=user_id, metric="weight_kg"))

    assert [e.value for e in entries] == [70.0, 68.0]
    assert entries[0].recorded_at < entries[1].recorded_at


async def test_empty_range_returns_empty_list():
    evolution = FakeEvolutionProjector()
    encryption = FakeDataEncryption()
    handler = GetEvolutionTimelineHandler(evolution, encryption)
    entries = await handler.handle(
        GetEvolutionTimelineQuery(user_id=uuid.uuid4(), metric="weight_kg")
    )
    assert entries == []
