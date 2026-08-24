"""Typed event payload shapes published by identity-service.

Data shapes only — no business logic (monorepo-tooling SKILL.md). Any
consuming service may use these for deserialization/validation, but must
never import identity-service's internal code directly.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserRegisteredPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    email: str
    registered_at: datetime
    email_verification_token_reference_id: UUID


class PasswordResetRequestedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    email: str
    reset_token_reference_id: UUID
    requested_at: datetime


class NewDeviceLoginDetectedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    device_fingerprint_hash: str
    occurred_at: datetime
    email: str
