"""Read-side DTOs returned by query handlers -- plain dataclasses, no
framework dependency (Pydantic mapping happens at the HTTP schema layer)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class ProfileSnapshotDTO:
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


@dataclass(frozen=True, slots=True)
class EvolutionEntryDTO:
    metric: str
    value: Any
    recorded_at: datetime
