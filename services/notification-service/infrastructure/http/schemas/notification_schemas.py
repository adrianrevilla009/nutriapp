"""Pydantic request/response schemas for the public notification-service
HTTP surface (api-conventions SKILL.md)."""

from __future__ import annotations

from datetime import time

from pydantic import BaseModel, ConfigDict, Field


class NotificationPreferenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    push_enabled: bool
    quiet_hours_start: time
    quiet_hours_end: time
    timezone: str


class NotificationPreferencesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferences: list[NotificationPreferenceItem]


class NotificationPreferencePatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str = Field(min_length=1)
    push_enabled: bool = True
    quiet_hours_start: time = time(22, 0)
    quiet_hours_end: time = time(8, 0)
    timezone: str = "UTC"


class DeviceRegistrationRequest(BaseModel):
    """Stub-only registration payload (implementation plan section 9.3):
    no mobile client exists yet, so this endpoint validates and accepts
    the request shape without a real device-lifecycle backing store."""

    model_config = ConfigDict(extra="forbid")

    device_token: str = Field(min_length=1)
    platform: str = Field(pattern="^(ios|android|web)$")


class DeviceRegistrationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
