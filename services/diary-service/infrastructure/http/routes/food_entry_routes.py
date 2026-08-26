"""POST/PATCH/DELETE/GET /api/v1/diary/food-entries routes. Thin
controllers only -- parse the request into a command/query DTO, call the
application handler, serialize the result (api-conventions SKILL.md). No
business logic here.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.correct_food_entry import (
    CorrectFoodEntryCommand,
    CorrectFoodEntryHandler,
)
from application.commands.delete_food_entry import DeleteFoodEntryCommand, DeleteFoodEntryHandler
from application.commands.log_food_entry import LogFoodEntryCommand, LogFoodEntryHandler
from application.queries.list_food_entries import ListFoodEntriesHandler, ListFoodEntriesQuery
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
    CorrectFoodEntryRequest,
    DeleteFoodEntryResponse,
    FoodEntryListItem,
    FoodEntryListResponse,
    FoodEntryResponse,
    FoodSourceSchema,
    LogFoodEntryRequest,
)
from infrastructure.persistence.postgres_event_store import PostgresEventStore
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from infrastructure.persistence.projectors.food_entries_projector import (
    PostgresFoodEntriesProjector,
)

router = APIRouter(prefix="/api/v1/diary/food-entries", tags=["food-entries"])


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
    response_model=FoodEntryResponse,
    summary="Log a food entry",
    description="Appends FoodEntryLogged (v1) -- see docs/events-catalog.md.",
)
async def log_food_entry(
    body: LogFoodEntryRequest,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    correlation_id: str = Depends(get_correlation_id),
) -> Any:
    event_store = PostgresEventStore(session)
    outbox = PostgresOutboxRepository(session)
    handler = LogFoodEntryHandler(event_store, outbox)
    try:
        result = await handler.handle(
            LogFoodEntryCommand(
                user_id=user_id,
                source=_to_domain_source(body.source),
                meal_slot=MealSlot.from_value(body.meal_slot),
                occurred_at=body.occurred_at,
                correlation_id=correlation_id,
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return FoodEntryResponse(
        entry_id=result.entry_id,
        user_id=result.user_id,
        source=body.source,
        meal_slot=result.meal_slot.value,
        occurred_at=result.occurred_at,
    )


@router.patch(
    "/{entry_id}",
    response_model=FoodEntryResponse,
    summary="Correct a previously logged food entry",
    description="Appends FoodEntryCorrected (v1) -- never mutates the original event.",
)
async def correct_food_entry(
    entry_id: uuid.UUID,
    body: CorrectFoodEntryRequest,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    correlation_id: str = Depends(get_correlation_id),
) -> Any:
    event_store = PostgresEventStore(session)
    outbox = PostgresOutboxRepository(session)
    handler = CorrectFoodEntryHandler(event_store, outbox)
    try:
        result = await handler.handle(
            CorrectFoodEntryCommand(
                entry_id=entry_id,
                user_id=user_id,
                source=_to_domain_source(body.source),
                meal_slot=MealSlot.from_value(body.meal_slot),
                occurred_at=body.occurred_at,
                correlation_id=correlation_id,
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return FoodEntryResponse(
        entry_id=result.entry_id,
        user_id=user_id,
        source=body.source,
        meal_slot=result.meal_slot.value,
        occurred_at=result.occurred_at,
    )


@router.delete(
    "/{entry_id}",
    response_model=DeleteFoodEntryResponse,
    summary="Delete a previously logged food entry",
    description="Appends FoodEntryDeleted (v1) -- never a destructive row delete.",
)
async def delete_food_entry(
    entry_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    correlation_id: str = Depends(get_correlation_id),
) -> Any:
    event_store = PostgresEventStore(session)
    outbox = PostgresOutboxRepository(session)
    handler = DeleteFoodEntryHandler(event_store, outbox)
    try:
        result = await handler.handle(
            DeleteFoodEntryCommand(
                entry_id=entry_id, user_id=user_id, correlation_id=correlation_id
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return DeleteFoodEntryResponse(entry_id=result.entry_id, deleted=result.deleted)


@router.get(
    "",
    response_model=FoodEntryListResponse,
    summary="List the authenticated user's food entries",
    description="Reads the food_entries_view read model, never replays the event stream.",
)
async def list_food_entries(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
) -> Any:
    read_port = PostgresFoodEntriesProjector(session)
    handler = ListFoodEntriesHandler(read_port)
    dtos = await handler.handle(
        ListFoodEntriesQuery(user_id=user_id, from_date=from_date, to_date=to_date)
    )
    return FoodEntryListResponse(
        entries=[
            FoodEntryListItem(
                entry_id=dto.entry_id,
                source=dto.source,
                meal_slot=dto.meal_slot,
                occurred_at=dto.occurred_at,
                deleted=dto.deleted,
            )
            for dto in dtos
        ]
    )
