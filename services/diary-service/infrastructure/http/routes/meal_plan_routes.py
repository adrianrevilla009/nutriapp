"""POST/PATCH/DELETE/GET /api/v1/diary/meal-plan routes."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.plan_meal import PlanMealCommand, PlanMealHandler
from application.commands.remove_meal_plan import RemoveMealPlanCommand, RemoveMealPlanHandler
from application.commands.update_meal_plan import UpdateMealPlanCommand, UpdateMealPlanHandler
from application.queries.get_meal_plan_calendar import (
    GetMealPlanCalendarHandler,
    GetMealPlanCalendarQuery,
)
from domain.value_objects.food_source import FoodSource, FoodSourceSnapshot
from domain.value_objects.macro_snapshot import MacroSnapshot
from domain.value_objects.meal_slot import MealSlot
from infrastructure.http.dependencies import (
    get_authenticated_user_id,
    get_correlation_id,
    get_session,
)
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.diary_schemas import (
    FoodSourceSchema,
    MealPlanCalendarItem,
    MealPlanCalendarResponse,
    MealPlanResponse,
    PlanMealRequest,
    RemoveMealPlanResponse,
    UpdateMealPlanRequest,
)
from infrastructure.persistence.postgres_event_store import PostgresEventStore
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from infrastructure.persistence.projectors.meal_plan_projector import PostgresMealPlanProjector

router = APIRouter(prefix="/api/v1/diary/meal-plan", tags=["meal-plan"])


def _to_domain_source(schema: FoodSourceSchema) -> FoodSource:
    return FoodSource(
        source_type=schema.source_type,
        source_reference_id=schema.source_reference_id,
        snapshot=FoodSourceSnapshot(
            name=schema.snapshot.name,
            brand=schema.snapshot.brand,
            quantity=schema.snapshot.quantity,
            unit=schema.snapshot.unit,
            macros_per_unit=MacroSnapshot(
                calories_kcal=schema.snapshot.macros_per_unit.calories_kcal,
                protein_g=schema.snapshot.macros_per_unit.protein_g,
                carbs_g=schema.snapshot.macros_per_unit.carbs_g,
                fat_g=schema.snapshot.macros_per_unit.fat_g,
            ),
        ),
    )


@router.post(
    "",
    response_model=MealPlanResponse,
    summary="Schedule a planned (future) meal entry",
    description="Appends MealPlanned (v1) -- distinct from the as-eaten food entry log.",
)
async def plan_meal(
    body: PlanMealRequest,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    correlation_id: str = Depends(get_correlation_id),
) -> Any:
    event_store = PostgresEventStore(session)
    outbox = PostgresOutboxRepository(session)
    handler = PlanMealHandler(event_store, outbox)
    try:
        result = await handler.handle(
            PlanMealCommand(
                user_id=user_id,
                source=_to_domain_source(body.source),
                meal_slot=MealSlot.from_value(body.meal_slot),
                planned_for=body.planned_for,
                correlation_id=correlation_id,
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return MealPlanResponse(
        plan_entry_id=result.plan_entry_id,
        source=body.source,
        meal_slot=result.meal_slot.value,
        planned_for=result.planned_for,
    )


@router.patch(
    "/{plan_entry_id}",
    response_model=MealPlanResponse,
    summary="Update a planned meal entry",
    description="Appends MealPlanUpdated (v1) -- never mutates the original event.",
)
async def update_meal_plan(
    plan_entry_id: uuid.UUID,
    body: UpdateMealPlanRequest,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    correlation_id: str = Depends(get_correlation_id),
) -> Any:
    event_store = PostgresEventStore(session)
    outbox = PostgresOutboxRepository(session)
    handler = UpdateMealPlanHandler(event_store, outbox)
    try:
        result = await handler.handle(
            UpdateMealPlanCommand(
                plan_entry_id=plan_entry_id,
                user_id=user_id,
                source=_to_domain_source(body.source),
                meal_slot=MealSlot.from_value(body.meal_slot),
                planned_for=body.planned_for,
                correlation_id=correlation_id,
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return MealPlanResponse(
        plan_entry_id=result.plan_entry_id,
        source=body.source,
        meal_slot=result.meal_slot.value,
        planned_for=result.planned_for,
    )


@router.delete(
    "/{plan_entry_id}",
    response_model=RemoveMealPlanResponse,
    summary="Remove a planned meal entry",
    description="Appends MealPlanRemoved (v1) -- never a destructive row delete.",
)
async def remove_meal_plan(
    plan_entry_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    correlation_id: str = Depends(get_correlation_id),
) -> Any:
    event_store = PostgresEventStore(session)
    outbox = PostgresOutboxRepository(session)
    handler = RemoveMealPlanHandler(event_store, outbox)
    try:
        result = await handler.handle(
            RemoveMealPlanCommand(
                plan_entry_id=plan_entry_id, user_id=user_id, correlation_id=correlation_id
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return RemoveMealPlanResponse(plan_entry_id=result.plan_entry_id, removed=result.removed)


@router.get(
    "",
    response_model=MealPlanCalendarResponse,
    summary="Get the authenticated user's meal plan calendar",
    description="Reads the meal_plan_view read model, never replays the event stream.",
)
async def get_meal_plan_calendar(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
) -> Any:
    read_port = PostgresMealPlanProjector(session)
    handler = GetMealPlanCalendarHandler(read_port)
    dtos = await handler.handle(
        GetMealPlanCalendarQuery(user_id=user_id, from_date=from_date, to_date=to_date)
    )
    return MealPlanCalendarResponse(
        entries=[
            MealPlanCalendarItem(
                plan_entry_id=dto.plan_entry_id,
                source=dto.source,
                meal_slot=dto.meal_slot,
                planned_for=dto.planned_for,
                removed=dto.removed,
            )
            for dto in dtos
        ]
    )
