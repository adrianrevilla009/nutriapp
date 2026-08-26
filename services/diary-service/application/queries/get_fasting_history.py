"""GetFastingHistoryQuery + handler -- reads the fasting_windows_view read
model, never replays the event stream on a read."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from application.dto.diary_dto import FastingWindowDTO
from domain.ports.fasting_windows_read_port import FastingWindowsReadPort


@dataclass(frozen=True, slots=True)
class GetFastingHistoryQuery:
    user_id: uuid.UUID
    limit: int = 50


class GetFastingHistoryHandler:
    def __init__(self, read_port: FastingWindowsReadPort) -> None:
        self._read_port = read_port

    async def handle(self, query: GetFastingHistoryQuery) -> list[FastingWindowDTO]:
        rows = await self._read_port.get_history(query.user_id, query.limit)
        return [
            FastingWindowDTO(
                window_id=row["window_id"],
                user_id=row["user_id"],
                started_at=row["started_at"],
                ended_at=row["ended_at"],
            )
            for row in rows
        ]
