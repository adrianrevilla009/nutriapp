"""`GET /api/v1/analytics/trends/weekly` -- **not Pro-gated** (implementation
plan section 1 acceptance criterion 2). JWT-authenticated via
packages/shared-contracts' centralized dependency."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from application.queries.get_weekly_trend import (
    DEFAULT_WINDOW_DAYS,
    GetWeeklyTrendHandler,
    GetWeeklyTrendQuery,
)
from infrastructure.composition_root import build_repositories
from infrastructure.http.dependencies import get_authenticated_user_id, get_session
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.analytics_schemas import (
    WeeklyTrendResponse,
    weekly_trend_to_response,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get(
    "/trends/weekly",
    response_model=WeeklyTrendResponse,
    summary="Logging streak and macro/water running totals (not Pro-gated)",
)
async def get_weekly_trend(
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    window_days: Annotated[int, Query(ge=1)] = DEFAULT_WINDOW_DAYS,
) -> WeeklyTrendResponse | JSONResponse:
    daily_log_summary, _mw, _aa, _ec, _ea, _ob = build_repositories(session)
    handler = GetWeeklyTrendHandler(daily_log_summary)
    try:
        result = await handler.handle(
            GetWeeklyTrendQuery(
                user_id=user_id, as_of=datetime.now(timezone.utc).date(), window_days=window_days
            )
        )
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return weekly_trend_to_response(result)
