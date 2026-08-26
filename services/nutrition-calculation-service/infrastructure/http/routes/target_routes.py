"""GET /api/v1/nutrition/target, GET /api/v1/nutrition/target/history."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from application.queries.get_current_nutrition_target import (
    GetCurrentNutritionTargetHandler,
    GetCurrentNutritionTargetQuery,
)
from application.queries.get_target_history import GetTargetHistoryHandler, GetTargetHistoryQuery
from infrastructure.composition_root import Container
from infrastructure.http.dependencies import get_authenticated_user_id, get_container, get_session
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.nutrition_schemas import (
    NutritionTargetHistoryResponse,
    NutritionTargetResponse,
    target_dto_to_response,
)
from infrastructure.persistence.postgres_nutrition_target_repository import (
    PostgresNutritionTargetRepository,
)
from infrastructure.persistence.postgres_target_history_repository import (
    PostgresTargetHistoryRepository,
)

router = APIRouter(prefix="/api/v1/nutrition", tags=["nutrition-target"])


@router.get(
    "/target",
    response_model=NutritionTargetResponse,
    summary="Get the authenticated user's current calorie/macro target",
)
async def get_current_target(
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    container: Container = Depends(get_container),
) -> NutritionTargetResponse | JSONResponse:
    repository = PostgresNutritionTargetRepository(session)
    handler = GetCurrentNutritionTargetHandler(repository, cache=container.current_target_cache)
    try:
        dto = await handler.handle(GetCurrentNutritionTargetQuery(user_id=user_id))
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return target_dto_to_response(dto)


@router.get(
    "/target/history",
    response_model=NutritionTargetHistoryResponse,
    summary="Get the authenticated user's nutrition-target timeline",
)
async def get_target_history(
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
) -> NutritionTargetHistoryResponse | JSONResponse:
    repository = PostgresTargetHistoryRepository(session)
    handler = GetTargetHistoryHandler(repository)
    try:
        dtos = await handler.handle(GetTargetHistoryQuery(user_id=user_id))
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return NutritionTargetHistoryResponse(history=[target_dto_to_response(dto) for dto in dtos])
