"""Pydantic v2 request/response models for /api/v1/profile (api-conventions
SKILL.md). No response ever contains a raw event-store ciphertext -- query
handlers always decrypt before this layer serializes a response."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error: str
    code: str


class ConsentGrantResponse(BaseModel):
    consent_granted: bool


class WeightRecordRequest(BaseModel):
    weight_kg: float = Field(gt=0)


class WeightRecordResponse(BaseModel):
    weight_kg: float


class BodyMetricRecordRequest(BaseModel):
    metric_type: str
    value: float | int | str


class BodyMetricRecordResponse(BaseModel):
    metric_type: str
    value: float | int | str


class GoalRequest(BaseModel):
    goal_type: str
    target_value: float | None = None
    target_date: date | None = None


class GoalSetResponse(BaseModel):
    goal_type: str
    target_value: float | None
    target_date: date | None


class GoalUpdateResponse(GoalSetResponse):
    previous_goal_type: str


class ProfileSnapshotResponse(BaseModel):
    user_id: uuid.UUID
    consent_granted: bool
    weight_kg: float | None
    height_cm: float | None
    age: int | None
    sex: str | None
    activity_level: str | None
    goal_type: str | None
    goal_target_value: float | None
    goal_target_date: date | None


class EvolutionEntryResponse(BaseModel):
    metric: str
    value: float | int | str
    recorded_at: datetime


class EvolutionResponse(BaseModel):
    entries: list[EvolutionEntryResponse]
