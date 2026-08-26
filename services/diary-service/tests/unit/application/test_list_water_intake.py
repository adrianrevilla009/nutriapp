from __future__ import annotations

import uuid
from datetime import datetime, timezone

from application.queries.list_water_intake import ListWaterIntakeHandler, ListWaterIntakeQuery
from tests.fixtures.factories import FakeWaterIntakeReadPort

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


async def test_list_water_intake_maps_rows_to_dtos():
    user_id = uuid.uuid4()
    read_port = FakeWaterIntakeReadPort()
    read_port.rows.append(
        dict(
            intake_id=uuid.uuid4(), user_id=user_id, amount_ml=250.0, occurred_at=NOW, removed=False
        )
    )
    handler = ListWaterIntakeHandler(read_port)
    dtos = await handler.handle(ListWaterIntakeQuery(user_id=user_id))
    assert len(dtos) == 1
    assert dtos[0].amount_ml == 250.0
