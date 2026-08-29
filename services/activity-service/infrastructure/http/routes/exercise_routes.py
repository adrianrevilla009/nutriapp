"""POST/PATCH/DELETE/GET on /api/v1/activity/exercises -- the four public
HTTP routes this service exposes (implementation plan section 1,
acceptance criteria 1-4)."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.delete_exercise import DeleteExerciseCommand, DeleteExerciseHandler
from application.commands.log_exercise import LogExerciseCommand, LogExerciseHandler
from application.commands.update_exercise import UpdateExerciseCommand, UpdateExerciseHandler
from application.queries.list_exercises_for_date import (
    ListExercisesForDateHandler,
    ListExercisesForDateQuery,
)
from infrastructure.composition_root import build_repositories
from infrastructure.http.dependencies import (
    get_authenticated_user_id,
    get_correlation_id,
    get_session,
)
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.exercise_schemas import (
    ExerciseEntryResponse,
    ListExercisesResponse,
    LogExerciseRequest,
    UpdateExerciseRequest,
    entry_to_response,
)

router = APIRouter(prefix="/api/v1/activity/exercises", tags=["activity"])


@router.post(
    "",
    response_model=ExerciseEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log a manual exercise entry",
)
async def log_exercise(
    body: LogExerciseRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
) -> ExerciseEntryResponse | JSONResponse:
    exercise_repo, outbox_repo = build_repositories(session)
    handler = LogExerciseHandler(repository=exercise_repo, outbox_repository=outbox_repo)
    try:
        result = await handler.handle(
            LogExerciseCommand(
                user_id=user_id,
                exercise_type=body.exercise_type,
                duration_minutes=body.duration_minutes,
                calories_burned_kcal=body.calories_burned_kcal,
                occurred_at=body.occurred_at,
                correlation_id=correlation_id,
                label=body.label,
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return entry_to_response(result.entry)


@router.patch(
    "/{entry_id}",
    response_model=ExerciseEntryResponse,
    summary="Correct a previously logged exercise entry",
)
async def update_exercise(
    entry_id: uuid.UUID,
    body: UpdateExerciseRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    correlation_id: Annotated[str, Depends(get_correlation_id)],
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
) -> ExerciseEntryResponse | JSONResponse:
    exercise_repo, outbox_repo = build_repositories(session)
    handler = UpdateExerciseHandler(repository=exercise_repo, outbox_repository=outbox_repo)
    command = UpdateExerciseCommand(
        entry_id=entry_id,
        user_id=user_id,
        correlation_id=correlation_id,
        exercise_type=body.exercise_type,
        duration_minutes=body.duration_minutes,
        calories_burned_kcal=body.calories_burned_kcal,
        occurred_at=body.occurred_at,
    )
    # PATCH semantics: only override `label` at all when the request body
    # actually included the key -- leaving `command.label` at its own
    # dataclass default ("not supplied" sentinel) otherwise distinguishes
    # "not supplied" (leave unchanged) from an explicit `"label": null`
    # (clear it), which `model_fields_set` captures (test-plan section
    # 1/3).
    if "label" in body.model_fields_set:
        command = replace(command, label=body.label)
    try:
        result = await handler.handle(command)
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return entry_to_response(result.entry)


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    # No response body on success (a 204 must not have one); an error
    # path may still return a JSON error body via `map_exception`, so
    # `response_model` cannot be inferred from the return type annotation.
    response_model=None,
    summary="Soft-delete a previously logged exercise entry (idempotent)",
)
async def delete_exercise(
    entry_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
) -> Response | JSONResponse:
    exercise_repo, _outbox_repo = build_repositories(session)
    handler = DeleteExerciseHandler(repository=exercise_repo)
    try:
        await handler.handle(DeleteExerciseCommand(entry_id=entry_id, user_id=user_id))
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "",
    response_model=ListExercisesResponse,
    summary="List the authenticated user's exercise entries for a given date",
)
async def list_exercises(
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
    occurred_on: Annotated[date, Query(alias="date")],
) -> ListExercisesResponse:
    exercise_repo, _outbox_repo = build_repositories(session)
    handler = ListExercisesForDateHandler(repository=exercise_repo)
    entries = await handler.handle(
        ListExercisesForDateQuery(user_id=user_id, occurred_on=occurred_on)
    )
    return ListExercisesResponse(entries=[entry_to_response(e) for e in entries])
