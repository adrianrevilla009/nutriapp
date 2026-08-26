"""GetDailySummaryQuery + handler -- cache-aside via DailySummaryCachePort,
falls through to DailySummaryReadPort on a miss (implementation plan
section 7: TTL 60s, event-driven invalidation on the write side)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from application.dto.diary_dto import DailySummaryDTO
from domain.ports.daily_summary_cache_port import DailySummaryCachePort
from domain.ports.daily_summary_read_port import DailySummaryReadPort


@dataclass(frozen=True, slots=True)
class GetDailySummaryQuery:
    user_id: uuid.UUID
    summary_date: date


class GetDailySummaryHandler:
    def __init__(self, read_port: DailySummaryReadPort, cache_port: DailySummaryCachePort) -> None:
        self._read_port = read_port
        self._cache_port = cache_port

    async def handle(self, query: GetDailySummaryQuery) -> DailySummaryDTO:
        cached = await self._cache_port.get(query.user_id, query.summary_date)
        if cached is not None:
            return _to_dto(query.user_id, query.summary_date, cached)

        row = await self._read_port.get_summary(query.user_id, query.summary_date)
        if row is None:
            return DailySummaryDTO(
                user_id=query.user_id,
                summary_date=query.summary_date,
                total_calories_kcal=0.0,
                total_protein_g=0.0,
                total_carbs_g=0.0,
                total_fat_g=0.0,
                total_water_ml=0.0,
                fasting_windows_ended=0,
            )

        await self._cache_port.set(query.user_id, query.summary_date, row)
        return _to_dto(query.user_id, query.summary_date, row)


def _to_dto(user_id: uuid.UUID, summary_date: date, row: dict[str, Any]) -> DailySummaryDTO:
    return DailySummaryDTO(
        user_id=user_id,
        summary_date=summary_date,
        total_calories_kcal=float(row["total_calories_kcal"]),
        total_protein_g=float(row["total_protein_g"]),
        total_carbs_g=float(row["total_carbs_g"]),
        total_fat_g=float(row["total_fat_g"]),
        total_water_ml=float(row["total_water_ml"]),
        fasting_windows_ended=int(row["fasting_windows_ended"]),
    )
