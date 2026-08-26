"""Read-side DTOs returned by query handlers and write-side result DTOs
returned by command handlers -- plain dataclasses, no framework
dependency (Pydantic mapping happens at the HTTP schema layer)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class FoodEntryDTO:
    entry_id: uuid.UUID
    user_id: uuid.UUID
    source: dict[str, Any]
    meal_slot: str
    occurred_at: datetime
    deleted: bool


@dataclass(frozen=True, slots=True)
class WaterIntakeDTO:
    intake_id: uuid.UUID
    user_id: uuid.UUID
    amount_ml: float
    occurred_at: datetime
    removed: bool


@dataclass(frozen=True, slots=True)
class FastingWindowDTO:
    window_id: uuid.UUID
    user_id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None


@dataclass(frozen=True, slots=True)
class MealPlanEntryDTO:
    plan_entry_id: uuid.UUID
    user_id: uuid.UUID
    source: dict[str, Any]
    meal_slot: str
    planned_for: datetime
    removed: bool


@dataclass(frozen=True, slots=True)
class DailySummaryDTO:
    user_id: uuid.UUID
    summary_date: date
    total_calories_kcal: float
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    total_water_ml: float
    fasting_windows_ended: int
