from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from application.queries.get_meal_plan_calendar import (
    GetMealPlanCalendarHandler,
    GetMealPlanCalendarQuery,
)
from tests.fixtures.factories import FakeMealPlanReadPort

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


async def test_get_meal_plan_calendar_maps_rows_to_dtos():
    user_id = uuid.uuid4()
    read_port = FakeMealPlanReadPort()
    read_port.rows.append(
        dict(
            plan_entry_id=uuid.uuid4(),
            user_id=user_id,
            source={"source_type": "catalog_product"},
            meal_slot="dinner",
            planned_for=NOW,
            removed=False,
        )
    )
    handler = GetMealPlanCalendarHandler(read_port)
    dtos = await handler.handle(
        GetMealPlanCalendarQuery(
            user_id=user_id, from_date=date(2026, 8, 1), to_date=date(2026, 8, 31)
        )
    )
    assert len(dtos) == 1
    assert dtos[0].meal_slot == "dinner"
