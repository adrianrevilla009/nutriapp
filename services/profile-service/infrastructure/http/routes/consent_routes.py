"""POST /api/v1/profile/consent -- explicit, specific consent to collect
biometric/health data (CLAUDE.md section 8), required before any metric
can be written."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.grant_biometric_consent import (
    GrantBiometricConsentCommand,
    GrantBiometricConsentHandler,
)
from infrastructure.http.dependencies import (
    get_authenticated_user_id,
    get_correlation_id,
    get_session,
)
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.profile_schemas import ConsentGrantResponse
from infrastructure.persistence.postgres_event_store import PostgresEventStore
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from infrastructure.persistence.postgres_snapshot_projector import PostgresSnapshotProjector

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


@router.post(
    "/consent",
    response_model=ConsentGrantResponse,
    summary="Grant explicit consent to collect biometric/health data",
    description="Required before any metric-recording endpoint can be used. "
    "Idempotent -- safe to call twice.",
)
async def grant_consent(
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    correlation_id: str = Depends(get_correlation_id),
) -> Any:
    event_store = PostgresEventStore(session)
    outbox = PostgresOutboxRepository(session)
    snapshot_projector = PostgresSnapshotProjector(session)
    handler = GrantBiometricConsentHandler(event_store, outbox, snapshot_projector)
    try:
        result = await handler.handle(
            GrantBiometricConsentCommand(user_id=user_id, correlation_id=correlation_id)
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001 -- mapped centrally below
        await session.rollback()
        return map_exception(exc)
    return ConsentGrantResponse(consent_granted=result.consent_granted)
