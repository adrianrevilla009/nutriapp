"""GET/PATCH /api/v1/notifications/preferences (implementation plan
section 1, acceptance criterion 3) plus the stubbed
POST /api/v1/notifications/devices (section 9.3) -- kept in this same
module since the approved plan's file list (section 3) only names
preferences_routes.py/provider_webhook_routes.py/health.py under
infrastructure/http/routes/, and device registration is not a full
feature in this plan, just the plumbing shape for a future mobile
client. JWT-authenticated via the shared-contracts centralized auth
dependency (ADR-0022, commit 4248242).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.update_notification_preferences import (
    UpdateNotificationPreferencesCommand,
    UpdateNotificationPreferencesHandler,
)
from application.errors import InvalidPreferenceUpdateError
from application.queries.get_notification_preferences import (
    GetNotificationPreferencesHandler,
    GetNotificationPreferencesQuery,
)
from infrastructure.composition_root import build_preferences_repository
from infrastructure.http.dependencies import get_authenticated_user_id, get_session
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.notification_schemas import (
    DeviceRegistrationRequest,
    DeviceRegistrationResponse,
    NotificationPreferenceItem,
    NotificationPreferencePatchRequest,
    NotificationPreferencesResponse,
)

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_preferences(
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    session: AsyncSession = Depends(get_session),
) -> NotificationPreferencesResponse:
    repository = build_preferences_repository(session)
    handler = GetNotificationPreferencesHandler(repository)
    preferences = await handler.handle(GetNotificationPreferencesQuery(user_id=user_id))
    return NotificationPreferencesResponse(
        preferences=[
            NotificationPreferenceItem(
                category=pref.category.name,
                push_enabled=pref.push_enabled,
                quiet_hours_start=pref.quiet_hours.start,
                quiet_hours_end=pref.quiet_hours.end,
                timezone=pref.quiet_hours.tz,
            )
            for pref in preferences
        ]
    )


@router.patch("/preferences", response_model=NotificationPreferenceItem)
async def patch_preferences(
    body: NotificationPreferencePatchRequest,
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
    session: AsyncSession = Depends(get_session),
) -> Any:
    repository = build_preferences_repository(session)
    handler = UpdateNotificationPreferencesHandler(repository)
    try:
        preference = await handler.handle(
            UpdateNotificationPreferencesCommand(
                user_id=user_id,
                category=body.category,
                push_enabled=body.push_enabled,
                quiet_hours_start=body.quiet_hours_start,
                quiet_hours_end=body.quiet_hours_end,
                timezone=body.timezone,
            )
        )
        await session.commit()
    except InvalidPreferenceUpdateError as exc:
        await session.rollback()
        return map_exception(exc)
    return NotificationPreferenceItem(
        category=preference.category.name,
        push_enabled=preference.push_enabled,
        quiet_hours_start=preference.quiet_hours.start,
        quiet_hours_end=preference.quiet_hours.end,
        timezone=preference.quiet_hours.tz,
    )


@router.post("/devices", response_model=DeviceRegistrationResponse)
async def register_device(
    body: DeviceRegistrationRequest,
    user_id: uuid.UUID = Depends(get_authenticated_user_id),
) -> DeviceRegistrationResponse:
    # Registration plumbing only (implementation plan section 9.3) -- no
    # device_tokens table exists in this plan's migration scope; nothing
    # downstream is asserted or triggered by this call yet.
    return DeviceRegistrationResponse(accepted=True)
