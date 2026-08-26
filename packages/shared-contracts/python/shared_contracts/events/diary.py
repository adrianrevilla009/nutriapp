"""Typed event payload shapes published by diary-service.

Data shapes only -- no business logic (monorepo-tooling SKILL.md). Any
consuming service (nutrition-calculation-service, analytics-service) may
use these for deserialization/validation, but must never import
diary-service's internal code directly.

`FoodSourcePayloadV1` is the shared, minimally-generic discriminated shape
used by both FoodEntry* and MealPlan* events (implementation plan
section 5) -- `source_type` reserves `recipe` and `ai_detected` for later
services (recipe-service, food-recognition-service); no adapter produces
those values yet.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MacroSnapshotPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


class FoodSourceSnapshotPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    brand: str | None
    quantity: float
    unit: str
    macros_per_unit: MacroSnapshotPayloadV1


class FoodSourcePayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str
    source_reference_id: str
    snapshot: FoodSourceSnapshotPayloadV1


class FoodEntryLoggedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: UUID
    user_id: UUID
    source: FoodSourcePayloadV1
    meal_slot: str
    occurred_at: datetime
    planned_from_entry_id: UUID | None = None


class FoodEntryCorrectedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: UUID
    user_id: UUID
    source: FoodSourcePayloadV1
    meal_slot: str
    occurred_at: datetime
    corrected_at: datetime


class FoodEntryDeletedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: UUID
    user_id: UUID
    deleted_at: datetime


class WaterIntakeLoggedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intake_id: UUID
    user_id: UUID
    amount_ml: float
    occurred_at: datetime


class WaterIntakeRemovedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intake_id: UUID
    user_id: UUID
    removed_at: datetime


class FastingWindowStartedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_id: UUID
    user_id: UUID
    started_at: datetime


class FastingWindowEndedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_id: UUID
    user_id: UUID
    ended_at: datetime


class MealPlannedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_entry_id: UUID
    user_id: UUID
    source: FoodSourcePayloadV1
    meal_slot: str
    planned_for: datetime


class MealPlanUpdatedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_entry_id: UUID
    user_id: UUID
    source: FoodSourcePayloadV1
    meal_slot: str
    planned_for: datetime
    updated_at: datetime


class MealPlanRemovedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_entry_id: UUID
    user_id: UUID
    removed_at: datetime
