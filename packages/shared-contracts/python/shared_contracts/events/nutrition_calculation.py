"""Typed event payload shapes published by nutrition-calculation-service.

Data shapes only -- no business logic (monorepo-tooling SKILL.md). Any
consuming service (analytics-service, nutrition-assistant-service --
documented in docs/events-catalog.md, none live yet) may use these for
deserialization/validation, but must never import
nutrition-calculation-service's internal code directly.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MacroAmountsPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


class ConfidenceRangePayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: float
    max: float


class NutritionValueRecomputedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    scope: str
    entry_id: UUID | None
    date: date | None
    macros: MacroAmountsPayloadV1
    micronutrients: dict[str, float | None] | None
    micronutrients_status: str
    is_estimated: bool
    confidence_range: ConfidenceRangePayloadV1 | None
    formula_version: str
    reason: str
    recomputed_at: datetime


class MacroTargetRangePayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protein_g_min: float
    protein_g_max: float
    fat_g_min: float
    carbs_g: float


class NutritionTargetUpdatedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    bmr_kcal: float
    tdee_kcal: float
    calorie_target_kcal: float
    macro_targets: MacroTargetRangePayloadV1
    # Nutrient-keyed minimum-target map (added additively, still v1 -- see
    # docs/events-catalog.md's NutritionTargetUpdated entry for the
    # versioning-decision reasoning). Defaults to `{}` (not required) so
    # an old-shaped payload published before this field existed still
    # validates -- genuine additive backward compatibility, not merely
    # assumed (see the contract test proving exactly this in
    # tests/contract/events/test_event_schemas.py). Always carries
    # `protein_g`/`fat_g`; as of Phase 2
    # (dri-rda-addendum.md) also carries `calcium_mg`/`iron_mg`/
    # `vitamin_c_mg` for adult users -- see
    # nutrition-calculation-service's
    # domain/services/nutrient_target_min_builder.py and
    # domain/services/micronutrient_dri_resolver.py.
    nutrient_targets_min: dict[str, float] = Field(default_factory=dict)
    goal_type: str
    activity_level: str
    activity_adjustment_kcal: float | None
    clamped: bool
    clamp_reason: str | None
    formula_version: str
    reason: str
    effective_from: datetime
