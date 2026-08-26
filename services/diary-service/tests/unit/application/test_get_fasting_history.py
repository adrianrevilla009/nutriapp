from __future__ import annotations

import uuid
from datetime import datetime, timezone

from application.queries.get_fasting_history import (
    GetFastingHistoryHandler,
    GetFastingHistoryQuery,
)
from tests.fixtures.factories import FakeFastingWindowsReadPort

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


async def test_get_fasting_history_maps_rows_to_dtos():
    user_id = uuid.uuid4()
    read_port = FakeFastingWindowsReadPort()
    read_port.rows.append(
        dict(window_id=uuid.uuid4(), user_id=user_id, started_at=NOW, ended_at=None)
    )
    handler = GetFastingHistoryHandler(read_port)
    dtos = await handler.handle(GetFastingHistoryQuery(user_id=user_id))
    assert len(dtos) == 1
    assert dtos[0].ended_at is None
