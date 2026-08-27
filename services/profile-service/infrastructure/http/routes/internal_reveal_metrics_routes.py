"""POST /internal/v1/profile/{user_id}/reveal-metrics -- internal-only,
never routed through Kong (implementation plan Addendum 2, requirement 3:
enforced at the NetworkPolicy/Helm level -- see
infra/k8s/charts/profile-service/values.yaml's second `networkPolicy`
ingress rule and this app's own dedicated internal-only ASGI app in
infrastructure/main.py, listening on a distinct port from the public API).

Called once per BMR/TDEE calculation by nutrition-calculation-service,
which cannot decrypt profile-service's per-user KMS-wrapped biometric data
on its own (ADR-0023). Every call, success or failure, writes exactly one
audit record (requirement 6) and one structured log line that never
contains a biometric field value (requirement 7).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from application.queries.get_biometric_snapshot_for_calculation import (
    GetBiometricSnapshotForCalculationHandler,
    GetBiometricSnapshotForCalculationQuery,
)
from infrastructure.composition_root import Container
from infrastructure.http.dependencies import (
    get_audit_session,
    get_container,
    get_correlation_id,
    get_session,
)
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.internal_schemas import BiometricSnapshotRevealResponse
from infrastructure.persistence.postgres_audit_repository import PostgresAuditRepository
from infrastructure.persistence.postgres_snapshot_projector import PostgresSnapshotProjector

router = APIRouter(prefix="/internal/v1/profile", tags=["internal"])


@router.post(
    "/{user_id}/reveal-metrics",
    response_model=BiometricSnapshotRevealResponse,
    summary="Reveal a user's plaintext biometric snapshot for BMR/TDEE calculation",
    description="Service-to-service only (nutrition-calculation-service). Never "
    "routed through Kong. Every attempt, success or failure, writes an audit "
    "record. Response is minimized to exactly 6 fields.",
)
async def reveal_metrics(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    audit_session: AsyncSession = Depends(get_audit_session),
    container: Container = Depends(get_container),
    correlation_id: str = Depends(get_correlation_id),
    x_internal_service_credential: str = Header(default=""),
) -> BiometricSnapshotRevealResponse | JSONResponse:
    snapshot_read = PostgresSnapshotProjector(session)
    audit_repository = PostgresAuditRepository(audit_session)
    handler = GetBiometricSnapshotForCalculationHandler(
        snapshot_read,
        container.encryption,
        audit_repository,
        container.rate_limiter,
        container.settings.reveal_caller_credentials,
        rate_limit=container.settings.reveal_rate_limit,
        rate_limit_window_seconds=container.settings.reveal_rate_limit_window_seconds,
    )
    try:
        result = await handler.handle(
            GetBiometricSnapshotForCalculationQuery(
                user_id=user_id,
                caller_service_credential=x_internal_service_credential,
                correlation_id=correlation_id,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return BiometricSnapshotRevealResponse(
        weight_kg=result.weight_kg,
        height_cm=result.height_cm,
        age=result.age,
        sex=result.sex,
        activity_level=result.activity_level,
        goal_type=result.goal_type,
    )
