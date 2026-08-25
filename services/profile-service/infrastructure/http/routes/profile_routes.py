"""POST/GET /api/v1/profile/* routes. Thin controllers only -- parse the
request into a command/query DTO, call the application handler, serialize
the result (api-conventions SKILL.md). No business logic here.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.record_body_metric import (
    RecordBodyMetricCommand,
    RecordBodyMetricHandler,
)
from application.commands.record_weight import RecordWeightCommand, RecordWeightHandler
from application.commands.set_goal import SetGoalCommand, SetGoalHandler
from application.commands.update_goal import UpdateGoalCommand, UpdateGoalHandler
from application.queries.get_evolution_timeline import (
    GetEvolutionTimelineHandler,
    GetEvolutionTimelineQuery,
)
from application.queries.get_profile_snapshot import (
    GetProfileSnapshotHandler,
    GetProfileSnapshotQuery,
)
from infrastructure.composition_root import Container
from infrastructure.http.dependencies import (
    get_authenticated_user_id,
    get_container,
    get_correlation_id,
    get_session,
)
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.profile_schemas import (
    BodyMetricRecordRequest,
    BodyMetricRecordResponse,
    EvolutionEntryResponse,
    EvolutionResponse,
    GoalRequest,
    GoalSetResponse,
    GoalUpdateResponse,
    ProfileSnapshotResponse,
    WeightRecordRequest,
    WeightRecordResponse,
)
from infrastructure.persistence.postgres_event_store import PostgresEventStore
from infrastructure.persistence.postgres_evolution_projector import PostgresEvolutionProjector
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from infrastructure.persistence.postgres_snapshot_projector import PostgresSnapshotProjector

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


@router.post(
    "/metrics/weight",
    response_model=WeightRecordResponse,
    summary="Record a weight reading",
    description="Requires consent to have been granted (403 otherwise).",
)
async def record_weight(
    body: WeightRecordRequest,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    container: Container = Depends(get_container),
    correlation_id: str = Depends(get_correlation_id),
):
    event_store = PostgresEventStore(session)
    outbox = PostgresOutboxRepository(session)
    snapshot_projector = PostgresSnapshotProjector(session)
    evolution_projector = PostgresEvolutionProjector(session)
    handler = RecordWeightHandler(
        event_store, outbox, snapshot_projector, evolution_projector, container.encryption
    )
    try:
        result = await handler.handle(
            RecordWeightCommand(
                user_id=user_id, weight_kg=body.weight_kg, correlation_id=correlation_id
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return WeightRecordResponse(weight_kg=result.weight_kg)


@router.post(
    "/metrics/body",
    response_model=BodyMetricRecordResponse,
    summary="Record a body metric (height, age, sex, or activity level)",
    description="Requires consent to have been granted (403 otherwise).",
)
async def record_body_metric(
    body: BodyMetricRecordRequest,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    container: Container = Depends(get_container),
    correlation_id: str = Depends(get_correlation_id),
):
    event_store = PostgresEventStore(session)
    outbox = PostgresOutboxRepository(session)
    snapshot_projector = PostgresSnapshotProjector(session)
    evolution_projector = PostgresEvolutionProjector(session)
    handler = RecordBodyMetricHandler(
        event_store, outbox, snapshot_projector, evolution_projector, container.encryption
    )
    try:
        result = await handler.handle(
            RecordBodyMetricCommand(
                user_id=user_id,
                metric_type=body.metric_type,
                value=body.value,
                correlation_id=correlation_id,
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return BodyMetricRecordResponse(metric_type=result.metric_type, value=result.value)


@router.post(
    "/goal",
    response_model=GoalSetResponse,
    summary="Set the user's goal",
    description="Create-only -- use PUT /goal to change an existing goal.",
)
async def set_goal(
    body: GoalRequest,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    container: Container = Depends(get_container),
    correlation_id: str = Depends(get_correlation_id),
):
    event_store = PostgresEventStore(session)
    outbox = PostgresOutboxRepository(session)
    snapshot_projector = PostgresSnapshotProjector(session)
    handler = SetGoalHandler(event_store, outbox, snapshot_projector, container.encryption)
    try:
        result = await handler.handle(
            SetGoalCommand(
                user_id=user_id,
                goal_type=body.goal_type,
                target_value=body.target_value,
                target_date=body.target_date,
                correlation_id=correlation_id,
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return GoalSetResponse(
        goal_type=result.goal_type,
        target_value=result.target_value,
        target_date=result.target_date,
    )


@router.put(
    "/goal",
    response_model=GoalUpdateResponse,
    summary="Update the user's existing goal",
    description="Requires an existing goal -- use POST /goal to create the first one.",
)
async def update_goal(
    body: GoalRequest,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    container: Container = Depends(get_container),
    correlation_id: str = Depends(get_correlation_id),
):
    event_store = PostgresEventStore(session)
    outbox = PostgresOutboxRepository(session)
    snapshot_projector = PostgresSnapshotProjector(session)
    handler = UpdateGoalHandler(event_store, outbox, snapshot_projector, container.encryption)
    try:
        result = await handler.handle(
            UpdateGoalCommand(
                user_id=user_id,
                goal_type=body.goal_type,
                target_value=body.target_value,
                target_date=body.target_date,
                correlation_id=correlation_id,
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return map_exception(exc)
    return GoalUpdateResponse(
        goal_type=result.goal_type,
        target_value=result.target_value,
        target_date=result.target_date,
        previous_goal_type=result.previous_goal_type,
    )


@router.get(
    "",
    response_model=ProfileSnapshotResponse,
    summary="Get the current profile snapshot",
    description="Reads the profile_snapshot read model -- never replays the "
    "event stream on a read. 404 if no profile exists yet for this user_id.",
)
async def get_profile(
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    container: Container = Depends(get_container),
):
    snapshot_projector = PostgresSnapshotProjector(session)
    handler = GetProfileSnapshotHandler(snapshot_projector, container.encryption)
    try:
        dto = await handler.handle(GetProfileSnapshotQuery(user_id=user_id))
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return ProfileSnapshotResponse(
        user_id=dto.user_id,
        consent_granted=dto.consent_granted,
        weight_kg=dto.weight_kg,
        height_cm=dto.height_cm,
        age=dto.age,
        sex=dto.sex,
        activity_level=dto.activity_level,
        goal_type=dto.goal_type,
        goal_target_value=dto.goal_target_value,
        goal_target_date=dto.goal_target_date,
    )


@router.get(
    "/evolution",
    response_model=EvolutionResponse,
    summary="Get the evolution timeline for a metric",
    description="Powers the user details panel's graphs -- reads the "
    "profile_evolution read model, never replays the event stream.",
)
async def get_evolution(
    metric: str = Query(...),
    from_ts: datetime | None = Query(None, alias="from"),
    to_ts: datetime | None = Query(None, alias="to"),
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    container: Container = Depends(get_container),
):
    evolution_projector = PostgresEvolutionProjector(session)
    handler = GetEvolutionTimelineHandler(evolution_projector, container.encryption)
    entries = await handler.handle(
        GetEvolutionTimelineQuery(user_id=user_id, metric=metric, from_ts=from_ts, to_ts=to_ts)
    )
    return EvolutionResponse(
        entries=[
            EvolutionEntryResponse(metric=e.metric, value=e.value, recorded_at=e.recorded_at)
            for e in entries
        ]
    )
