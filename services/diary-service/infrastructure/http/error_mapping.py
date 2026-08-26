"""Maps application/domain exceptions to the standard NutriApp error shape
(api-conventions SKILL.md): dict(error=..., code=...)."""

from __future__ import annotations

import structlog
from fastapi import status
from fastapi.responses import JSONResponse

from application.errors import (
    FoodEntryAccessDeniedError,
    FoodEntryNotFoundError,
    MealPlanAccessDeniedError,
    MealPlanEntryNotFoundError,
    WaterIntakeAccessDeniedError,
    WaterIntakeEntryNotFoundError,
)
from domain.entities.fasting_window import (
    OverlappingFastingWindowError,
    WindowAlreadyEndedError,
    WindowNotFoundError,
)
from domain.entities.food_entry import EntryAlreadyDeletedError
from domain.entities.meal_plan_entry import PlanEntryAlreadyRemovedError
from domain.entities.water_intake_entry import EntryAlreadyRemovedError
from domain.ports.event_store_port import OptimisticConcurrencyError
from domain.value_objects.food_source import InvalidFoodSourceError
from domain.value_objects.macro_snapshot import InvalidMacroSnapshotError
from domain.value_objects.meal_slot import InvalidMealSlotError
from domain.value_objects.quantity import InvalidQuantityError
from domain.value_objects.time_window import InvalidTimeWindowError
from domain.value_objects.water_amount_ml import InvalidWaterAmountError

logger = structlog.get_logger()


def error_response(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message, "code": code})


_MAPPING: list[tuple[type[Exception], int, str]] = [
    (FoodEntryNotFoundError, status.HTTP_404_NOT_FOUND, "FOOD_ENTRY_NOT_FOUND"),
    (FoodEntryAccessDeniedError, status.HTTP_403_FORBIDDEN, "FOOD_ENTRY_ACCESS_DENIED"),
    (EntryAlreadyDeletedError, status.HTTP_409_CONFLICT, "FOOD_ENTRY_ALREADY_DELETED"),
    (WaterIntakeEntryNotFoundError, status.HTTP_404_NOT_FOUND, "WATER_INTAKE_NOT_FOUND"),
    (WaterIntakeAccessDeniedError, status.HTTP_403_FORBIDDEN, "WATER_INTAKE_ACCESS_DENIED"),
    (EntryAlreadyRemovedError, status.HTTP_409_CONFLICT, "WATER_INTAKE_ALREADY_REMOVED"),
    (MealPlanEntryNotFoundError, status.HTTP_404_NOT_FOUND, "MEAL_PLAN_ENTRY_NOT_FOUND"),
    (MealPlanAccessDeniedError, status.HTTP_403_FORBIDDEN, "MEAL_PLAN_ACCESS_DENIED"),
    (PlanEntryAlreadyRemovedError, status.HTTP_409_CONFLICT, "MEAL_PLAN_ALREADY_REMOVED"),
    (OverlappingFastingWindowError, status.HTTP_409_CONFLICT, "FASTING_WINDOW_OVERLAP"),
    (WindowAlreadyEndedError, status.HTTP_409_CONFLICT, "FASTING_WINDOW_ALREADY_ENDED"),
    (WindowNotFoundError, status.HTTP_404_NOT_FOUND, "FASTING_WINDOW_NOT_FOUND"),
    (InvalidQuantityError, status.HTTP_400_BAD_REQUEST, "INVALID_QUANTITY"),
    (InvalidMealSlotError, status.HTTP_400_BAD_REQUEST, "INVALID_MEAL_SLOT"),
    (InvalidFoodSourceError, status.HTTP_400_BAD_REQUEST, "INVALID_FOOD_SOURCE"),
    (InvalidMacroSnapshotError, status.HTTP_400_BAD_REQUEST, "INVALID_MACRO_SNAPSHOT"),
    (InvalidWaterAmountError, status.HTTP_400_BAD_REQUEST, "INVALID_WATER_AMOUNT"),
    (InvalidTimeWindowError, status.HTTP_400_BAD_REQUEST, "INVALID_TIME_WINDOW"),
    (
        OptimisticConcurrencyError,
        status.HTTP_409_CONFLICT,
        "CONCURRENT_MODIFICATION",
    ),
]


def map_exception(exc: Exception) -> JSONResponse:
    for exc_type, status_code, code in _MAPPING:
        if isinstance(exc, exc_type):
            return error_response(status_code, str(exc) or code, code)
    logger.exception("unmapped_exception", exc_info=exc)
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred.", "INTERNAL_ERROR"
    )
