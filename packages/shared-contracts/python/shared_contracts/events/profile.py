"""Typed event payload shapes published by profile-service.

Data shapes only -- no business logic (monorepo-tooling SKILL.md). Any
consuming service may use these for deserialization/validation, but must
never import profile-service's internal code directly. Encrypted fields
(weight_kg, value, target_value) are typed `str` on the wire -- an
AES-256-GCM ciphertext (base64), never the plaintext number; only
profile-service itself, holding the per-user key, can decrypt them.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WeightRecordedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    weight_kg: str
    recorded_at: datetime


class BodyMetricRecordedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    metric_type: str
    value: str
    recorded_at: datetime


class GoalSetPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    goal_type: str
    target_value: str | None
    target_date: date | None
    set_at: datetime


class GoalUpdatedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    goal_type: str
    target_value: str | None
    target_date: date | None
    set_at: datetime
    previous_goal_type: str
