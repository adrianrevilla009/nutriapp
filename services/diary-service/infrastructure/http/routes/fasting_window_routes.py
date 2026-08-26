"""POST/GET /api/v1/diary/fasting-windows routes."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.end_fasting_window import (
    EndFastingWindowCommand,
    EndFastingWindowHandler,
)
from application.commands.start_fasting_window import (
    StartFastingWindowCommand,
    StartFastingWindowHandler,
)
from application.queries.get_fasting_history import (
    GetFastingHistoryHandler,
    GetFastingHistoryQuery,
)
from infrastructure.http.dependencies import (
    get_authenticated_user_id,
    get_correlation_id,
    get_session,
)
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.diary_schemas import (
    EndFastingWindowResponse,
    FastingHistoryResponse,
    FastingWindowHistoryItem,
    StartFastingWindowResponse,
)
from infrastructure.persistence.postgres_event_store import PostgresEventStore
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from infrastructure.persistence.projectors.fasting_windows_projector import (
    PostgresFastingWindowsProjector,
)

router = APIRouter(prefix="/api/v1/diary/fasting-windows", tags=["fasting-windows"])


@router.post(
    "/start",
    response_model=StartFastingWindowResponse,
    summary="Start a fasting window",
    description="Appends FastingWindowStarted (v1). Rejected with 409 if the user "
    "already has an open (unended) window.",
)
async def start_fasting_window(
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    correlation_id: str = Depends(get_correlation_id),
) -> Any:
    event_store = PostgresEventStore(session)
    outbox = PostgresOutboxRepository(session)
    handler = StartFastingWindowHandler(event_store, outbox)
    try:
        result = await handler.handle(
            StartFastingWindowCommand(user_id=user_id, correlation_id=correlation_id)
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return StartFastingWindowResponse(window_id=result.window_id, started_at=result.started_at)


@router.post(
    "/{window_id}/end",
    response_model=EndFastingWindowResponse,
    summary="End an open fasting window",
    description="Appends FastingWindowEnded (v1).",
)
async def end_fasting_window(
    window_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    correlation_id: str = Depends(get_correlation_id),
) -> Any:
    event_store = PostgresEventStore(session)
    outbox = PostgresOutboxRepository(session)
    handler = EndFastingWindowHandler(event_store, outbox)
    try:
        result = await handler.handle(
            EndFastingWindowCommand(
                user_id=user_id, window_id=window_id, correlation_id=correlation_id
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return EndFastingWindowResponse(window_id=result.window_id, ended_at=result.ended_at)


@router.get(
    "",
    response_model=FastingHistoryResponse,
    summary="Get the authenticated user's fasting window history",
    description="Reads the fasting_windows_view read model, never replays the event stream.",
)
async def get_fasting_history(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
) -> Any:
    read_port = PostgresFastingWindowsProjector(session)
    handler = GetFastingHistoryHandler(read_port)
    dtos = await handler.handle(GetFastingHistoryQuery(user_id=user_id, limit=limit))
    return FastingHistoryResponse(
        windows=[
            FastingWindowHistoryItem(
                window_id=dto.window_id, started_at=dto.started_at, ended_at=dto.ended_at
            )
            for dto in dtos
        ]
    )
