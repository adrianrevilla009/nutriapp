"""Typed event payload shapes published by food-recognition-service.

Data shapes only -- no business logic (monorepo-tooling SKILL.md). Any
consuming service (diary-service, documented as the eventual UI-facing
consumer per docs/events-catalog.md; no live consumer exists yet) may use
these for deserialization/validation, but must never import
food-recognition-service's internal code directly.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AnalysisStatus = Literal["detected", "uncertain", "unavailable"]


class FoodCandidatePayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    portion_range_min_g: float
    portion_range_max_g: float
    confidence: float


class FoodPhotoAnalyzedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: UUID
    candidates: list[FoodCandidatePayloadV1] = Field(max_length=3)
    model_version: str
    status: AnalysisStatus
