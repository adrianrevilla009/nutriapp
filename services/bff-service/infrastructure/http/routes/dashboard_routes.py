"""GET /api/v1/bff/dashboard -- the authenticated user's home/dashboard
screen (implementation plan section 1 acceptance criterion 1), covering
CLAUDE.md's E2E journey 1 ("register -> log a food item -> see macro/
micro totals"). Fans out three parallel calls
(application/queries/get_dashboard.py's GetDashboardHandler) to
diary-service and nutrition-calculation-service (x2); a failure on any
one degrades only that section, never the whole response (200 always,
never a 5xx for one dependency being down).

`get_authenticated_user_id` is resolved BEFORE the handler runs (a
FastAPI dependency, resolved before this function's body executes) --
a missing/invalid `Authorization` header yields 401 with zero downstream
requests ever attempted (test-plan section 3).
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request

from application.queries.get_dashboard import GetDashboardHandler, GetDashboardQuery
from infrastructure.composition_root import Container
from infrastructure.http.dependencies import get_authenticated_user_id, get_container
from infrastructure.http.schemas.dashboard_schemas import (
    DashboardResponse,
    dashboard_result_to_response,
)

router = APIRouter(prefix="/api/v1/bff", tags=["dashboard"])


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Get the authenticated user's dashboard screen",
    description=(
        "Aggregates diary-service's daily summary and nutrition-calculation-service's "
        "nutrient totals and active target for a single date, fanned out in parallel. "
        "Each of the three downstream calls is behind its own named circuit breaker, "
        "retry, and timeout; a failing or circuit-open call degrades only its own "
        'section to {"status": "unavailable"} -- never a 5xx for the whole screen '
        "(ADR-0008)."
    ),
)
async def get_dashboard(
    request: Request,
    dashboard_date: date = Query(..., alias="date"),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    container: Container = Depends(get_container),
) -> DashboardResponse:
    authorization_header = request.headers.get("Authorization", "")
    handler = GetDashboardHandler(
        diary_summary_port=container.diary_summary_client,
        nutrition_totals_port=container.nutrition_calculation_client,
        nutrition_target_port=container.nutrition_calculation_client,
    )
    result = await handler.handle(
        GetDashboardQuery(
            user_id=user_id,
            dashboard_date=dashboard_date,
            authorization_header=authorization_header,
        )
    )
    return dashboard_result_to_response(result)
