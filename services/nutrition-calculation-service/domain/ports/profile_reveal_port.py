"""ProfileRevealPort -- fetches plaintext biometric/goal metrics from
profile-service's internal reveal endpoint (implementation plan Addendum 1).

This port is the ONLY place this service ever sees plaintext weight/height/
age/sex/goal_type -- never from the encrypted `WeightRecorded`/
`BodyMetricRecorded`/`GoalSet`/`GoalUpdated` event payloads themselves
(those are triggers only, per Addendum 1). The result is never persisted
(see user_metrics_snapshot_port.py's docstring) -- it is used immediately
to compute a target and then discarded.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from domain.value_objects.activity_level import ActivityLevel
from domain.value_objects.goal_type import GoalType
from domain.value_objects.sex import Sex


@dataclass(frozen=True, slots=True)
class RevealedMetrics:
    weight_kg: float
    height_cm: float
    age: int
    sex: Sex
    activity_level: ActivityLevel
    goal_type: GoalType


class ProfileRevealUnavailableError(Exception):
    """Raised when profile-service's reveal endpoint cannot be reached
    (circuit open, retries exhausted, timeout) or reports the caller has no
    recorded metrics yet (404) or was rejected (401/403/429). The caller
    (RecomputeNutritionTargetHandler) must defer the recompute cleanly on
    this error -- never guess or default biometric values (implementation
    plan Addendum 1's security sub-addendum, requirement 7)."""


class ProfileRevealPort(Protocol):
    async def reveal(self, user_id: uuid.UUID) -> RevealedMetrics: ...
