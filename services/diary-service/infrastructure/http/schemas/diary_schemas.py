"""Pydantic v2 request/response models for /api/v1/diary (api-conventions
SKILL.md)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error: str
    code: str


class MacroSnapshotSchema(BaseModel):
    calories_kcal: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)


class FoodSourceSnapshotSchema(BaseModel):
    name: str
    brand: str | None = None
    quantity: float = Field(gt=0)
    unit: str
    macros_per_unit: MacroSnapshotSchema


class FoodSourceSchema(BaseModel):
    source_type: str
    source_reference_id: str
    snapshot: FoodSourceSnapshotSchema


class LogFoodEntryRequest(BaseModel):
    source: FoodSourceSchema
    meal_slot: str
    occurred_at: datetime


class CorrectFoodEntryRequest(BaseModel):
    source: FoodSourceSchema
    meal_slot: str
    occurred_at: datetime


class FoodEntryResponse(BaseModel):
    entry_id: uuid.UUID
    user_id: uuid.UUID
    source: FoodSourceSchema
    meal_slot: str
    occurred_at: datetime


class FoodEntryListItem(BaseModel):
    entry_id: uuid.UUID
    source: dict[str, Any]
    meal_slot: str
    occurred_at: datetime
    deleted: bool


class FoodEntryListResponse(BaseModel):
    entries: list[FoodEntryListItem]


class DeleteFoodEntryResponse(BaseModel):
    entry_id: uuid.UUID
    deleted: bool


class LogWaterIntakeRequest(BaseModel):
    amount_ml: float = Field(gt=0)
    occurred_at: datetime


class WaterIntakeResponse(BaseModel):
    intake_id: uuid.UUID
    amount_ml: float
    occurred_at: datetime


class RemoveWaterIntakeResponse(BaseModel):
    intake_id: uuid.UUID
    removed: bool


class WaterIntakeListItem(BaseModel):
    intake_id: uuid.UUID
    amount_ml: float
    occurred_at: datetime
    removed: bool


class WaterIntakeListResponse(BaseModel):
    entries: list[WaterIntakeListItem]


class StartFastingWindowResponse(BaseModel):
    window_id: uuid.UUID
    started_at: datetime


class EndFastingWindowResponse(BaseModel):
    window_id: uuid.UUID
    ended_at: datetime


class FastingWindowHistoryItem(BaseModel):
    window_id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None


class FastingHistoryResponse(BaseModel):
    windows: list[FastingWindowHistoryItem]


class PlanMealRequest(BaseModel):
    source: FoodSourceSchema
    meal_slot: str
    planned_for: datetime


class UpdateMealPlanRequest(BaseModel):
    source: FoodSourceSchema
    meal_slot: str
    planned_for: datetime


class MealPlanResponse(BaseModel):
    plan_entry_id: uuid.UUID
    source: FoodSourceSchema
    meal_slot: str
    planned_for: datetime


class RemoveMealPlanResponse(BaseModel):
    plan_entry_id: uuid.UUID
    removed: bool


class MealPlanCalendarItem(BaseModel):
    plan_entry_id: uuid.UUID
    source: dict[str, Any]
    meal_slot: str
    planned_for: datetime
    removed: bool


class MealPlanCalendarResponse(BaseModel):
    entries: list[MealPlanCalendarItem]


class DailySummaryResponse(BaseModel):
    user_id: uuid.UUID
    summary_date: date
    total_calories_kcal: float
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    total_water_ml: float
    fasting_windows_ended: int
