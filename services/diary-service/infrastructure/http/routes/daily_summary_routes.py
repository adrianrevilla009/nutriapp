"""GET /api/v1/diary/summary route -- the "today" screen's aggregate."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from application.queries.get_daily_summary import GetDailySummaryHandler, GetDailySummaryQuery
from infrastructure.composition_root import Container
from infrastructure.http.dependencies import (
    get_authenticated_user_id,
    get_container,
    get_session,
)
from infrastructure.http.schemas.diary_schemas import DailySummaryResponse
from infrastructure.persistence.projectors.daily_summary_projector import (
    PostgresDailySummaryProjector,
)

router = APIRouter(prefix="/api/v1/diary/summary", tags=["daily-summary"])


@router.get(
    "",
    response_model=DailySummaryResponse,
    summary="Get the authenticated user's daily summary",
    description="Cache-aside via Redis (diary:{user_id}:summary:{date}, TTL 60s), falling "
    "through to the daily_summary_view read model on a miss. Eventually consistent with a "
    "just-completed write (implementation plan section 9.1) -- command responses already "
    "return the newly-created/-corrected entry's own data.",
)
async def get_daily_summary(
    summary_date: date = Query(..., alias="date"),
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    container: Container = Depends(get_container),
) -> Any:
    read_port = PostgresDailySummaryProjector(session)
    handler = GetDailySummaryHandler(read_port, container.daily_summary_cache)
    dto = await handler.handle(GetDailySummaryQuery(user_id=user_id, summary_date=summary_date))
    return DailySummaryResponse(
        user_id=dto.user_id,
        summary_date=dto.summary_date,
        total_calories_kcal=dto.total_calories_kcal,
        total_protein_g=dto.total_protein_g,
        total_carbs_g=dto.total_carbs_g,
        total_fat_g=dto.total_fat_g,
        total_water_ml=dto.total_water_ml,
        fasting_windows_ended=dto.fasting_windows_ended,
    )
