"""Pydantic request/response schemas for the exercise HTTP surface
(api-conventions SKILL.md)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from domain.entities.exercise_entry import ExerciseEntry


class LogExerciseRequest(BaseModel):
    exercise_type: str
    duration_minutes: int
    calories_burned_kcal: float
    occurred_at: datetime
    label: str | None = None


class UpdateExerciseRequest(BaseModel):
    """PATCH semantics: only fields actually present in the request body
    are applied -- the route handler inspects `model_fields_set`, not
    just non-None values, so an explicit `"label": null` (clear it) is
    distinguishable from omitting `label` entirely (leave unchanged)."""

    exercise_type: str | None = None
    duration_minutes: int | None = None
    calories_burned_kcal: float | None = None
    occurred_at: datetime | None = None
    label: str | None = None


class ExerciseEntryResponse(BaseModel):
    entry_id: uuid.UUID
    exercise_type: str
    duration_minutes: int
    calories_burned_kcal: float
    occurred_at: datetime
    label: str | None
    created_at: datetime
    updated_at: datetime


class ListExercisesResponse(BaseModel):
    entries: list[ExerciseEntryResponse] = Field(default_factory=list)


def entry_to_response(entry: ExerciseEntry) -> ExerciseEntryResponse:
    return ExerciseEntryResponse(
        entry_id=entry.entry_id,
        exercise_type=entry.exercise_type.value,
        duration_minutes=int(entry.duration),
        calories_burned_kcal=float(entry.calories_burned),
        occurred_at=entry.occurred_at,
        label=entry.label,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )
