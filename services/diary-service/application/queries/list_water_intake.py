"""ListWaterIntakeQuery + handler -- reads the water_intake_view read
model, never replays the event stream on a read."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from application.dto.diary_dto import WaterIntakeDTO
from domain.ports.water_intake_read_port import WaterIntakeReadPort


@dataclass(frozen=True, slots=True)
class ListWaterIntakeQuery:
    user_id: uuid.UUID
    from_date: date | None = None
    to_date: date | None = None


class ListWaterIntakeHandler:
    def __init__(self, read_port: WaterIntakeReadPort) -> None:
        self._read_port = read_port

    async def handle(self, query: ListWaterIntakeQuery) -> list[WaterIntakeDTO]:
        rows = await self._read_port.list_intake(query.user_id, query.from_date, query.to_date)
        return [
            WaterIntakeDTO(
                intake_id=row["intake_id"],
                user_id=row["user_id"],
                amount_ml=row["amount_ml"],
                occurred_at=row["occurred_at"],
                removed=row["removed"],
            )
            for row in rows
        ]
