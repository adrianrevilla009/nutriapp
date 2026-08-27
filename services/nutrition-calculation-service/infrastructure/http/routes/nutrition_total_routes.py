"""GET /api/v1/nutrition/totals/{date}."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from application.queries.get_current_daily_total import (
    GetCurrentDailyTotalHandler,
    GetCurrentDailyTotalQuery,
)
from infrastructure.composition_root import Container
from infrastructure.http.dependencies import get_authenticated_user_id, get_container, get_session
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.nutrition_schemas import (
    NutrientTotalResponse,
    total_dto_to_response,
)
from infrastructure.persistence.postgres_daily_nutrition_total_repository import (
    PostgresDailyNutritionTotalRepository,
)

router = APIRouter(prefix="/api/v1/nutrition", tags=["nutrition-totals"])


@router.get(
    "/totals/{total_date}",
    response_model=NutrientTotalResponse,
    summary="Get the authenticated user's computed nutrient totals for a given date",
)
async def get_daily_total(
    total_date: date,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    container: Container = Depends(get_container),
) -> NutrientTotalResponse | JSONResponse:
    repository = PostgresDailyNutritionTotalRepository(session)
    handler = GetCurrentDailyTotalHandler(repository, cache=container.current_total_cache)
    try:
        dto = await handler.handle(
            GetCurrentDailyTotalQuery(user_id=user_id, total_date=total_date)
        )
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return total_dto_to_response(dto)
