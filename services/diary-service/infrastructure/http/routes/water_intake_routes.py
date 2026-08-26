"""POST/DELETE/GET /api/v1/diary/water-intake routes."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.log_water_intake import LogWaterIntakeCommand, LogWaterIntakeHandler
from application.commands.remove_water_intake import (
    RemoveWaterIntakeCommand,
    RemoveWaterIntakeHandler,
)
from application.queries.list_water_intake import ListWaterIntakeHandler, ListWaterIntakeQuery
from infrastructure.http.dependencies import (
    get_authenticated_user_id,
    get_correlation_id,
    get_session,
)
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.diary_schemas import (
    LogWaterIntakeRequest,
    RemoveWaterIntakeResponse,
    WaterIntakeListItem,
    WaterIntakeListResponse,
    WaterIntakeResponse,
)
from infrastructure.persistence.postgres_event_store import PostgresEventStore
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from infrastructure.persistence.projectors.water_intake_projector import (
    PostgresWaterIntakeProjector,
)

router = APIRouter(prefix="/api/v1/diary/water-intake", tags=["water-intake"])


@router.post(
    "",
    response_model=WaterIntakeResponse,
    summary="Log water intake",
    description="Appends WaterIntakeLogged (v1) -- see docs/events-catalog.md.",
)
async def log_water_intake(
    body: LogWaterIntakeRequest,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    correlation_id: str = Depends(get_correlation_id),
) -> Any:
    event_store = PostgresEventStore(session)
    outbox = PostgresOutboxRepository(session)
    handler = LogWaterIntakeHandler(event_store, outbox)
    try:
        result = await handler.handle(
            LogWaterIntakeCommand(
                user_id=user_id,
                amount_ml=body.amount_ml,
                occurred_at=body.occurred_at,
                correlation_id=correlation_id,
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return WaterIntakeResponse(
        intake_id=result.intake_id, amount_ml=result.amount_ml, occurred_at=result.occurred_at
    )


@router.delete(
    "/{intake_id}",
    response_model=RemoveWaterIntakeResponse,
    summary="Remove a previously logged water intake entry",
    description="Appends WaterIntakeRemoved (v1) -- never a destructive row delete.",
)
async def remove_water_intake(
    intake_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    correlation_id: str = Depends(get_correlation_id),
) -> Any:
    event_store = PostgresEventStore(session)
    outbox = PostgresOutboxRepository(session)
    handler = RemoveWaterIntakeHandler(event_store, outbox)
    try:
        result = await handler.handle(
            RemoveWaterIntakeCommand(
                intake_id=intake_id, user_id=user_id, correlation_id=correlation_id
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return RemoveWaterIntakeResponse(intake_id=result.intake_id, removed=result.removed)


@router.get(
    "",
    response_model=WaterIntakeListResponse,
    summary="List the authenticated user's water intake entries",
    description="Reads the water_intake_view read model, never replays the event stream.",
)
async def list_water_intake(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
) -> Any:
    read_port = PostgresWaterIntakeProjector(session)
    handler = ListWaterIntakeHandler(read_port)
    dtos = await handler.handle(
        ListWaterIntakeQuery(user_id=user_id, from_date=from_date, to_date=to_date)
    )
    return WaterIntakeListResponse(
        entries=[
            WaterIntakeListItem(
                intake_id=dto.intake_id,
                amount_ml=dto.amount_ml,
                occurred_at=dto.occurred_at,
                removed=dto.removed,
            )
            for dto in dtos
        ]
    )
