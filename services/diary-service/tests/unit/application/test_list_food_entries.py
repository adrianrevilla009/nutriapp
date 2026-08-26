from __future__ import annotations

import uuid
from datetime import datetime, timezone

from application.queries.list_food_entries import ListFoodEntriesHandler, ListFoodEntriesQuery
from tests.fixtures.factories import FakeFoodEntriesReadPort

NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


async def test_list_food_entries_maps_rows_to_dtos():
    user_id = uuid.uuid4()
    read_port = FakeFoodEntriesReadPort()
    read_port.rows.append(
        dict(
            entry_id=uuid.uuid4(),
            user_id=user_id,
            source={"source_type": "catalog_product"},
            meal_slot="breakfast",
            occurred_at=NOW,
            deleted=False,
        )
    )
    handler = ListFoodEntriesHandler(read_port)
    dtos = await handler.handle(ListFoodEntriesQuery(user_id=user_id))
    assert len(dtos) == 1
    assert dtos[0].meal_slot == "breakfast"
