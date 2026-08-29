"""NutritionTargetPort -- calls nutrition-calculation-service's existing
public `GET /api/v1/nutrition/target` endpoint (already-merged, no change
needed there). The incoming request's `Authorization` header is forwarded
unchanged.

Known upstream gap this port's contract deliberately encodes
(implementation plan section 1 acceptance criterion 3,
services/nutrition-calculation-service/README.md): a `Sex.OTHER` user, or
one whose target recompute is still deferred (a `ProfileRevealClient`
failure upstream), gets a well-formed `404 NUTRITION_TARGET_NOT_FOUND`
from that endpoint -- an EXPECTED, not exceptional, business response.
`get_target` returns `NutritionTargetNotComputedYet` (a plain value, not
a raised exception) for that case, so `GetDashboardHandler` can map it to
`{"status": "unavailable", "reason": "not_yet_computed"}`, distinct from
a genuine transport/5xx failure, which raises
`NutritionTargetUnavailableError` instead and maps to
`{"status": "unavailable", "reason": "downstream_error"}`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class NutritionTargetResult:
    calorie_target_kcal: float
    protein_g_min: float
    protein_g_max: float
    fat_g_min: float
    carbs_g: float
    goal_type: str


@dataclass(frozen=True, slots=True)
class NutritionTargetNotComputedYet:
    """Sentinel result: nutrition-calculation-service responded normally
    (404 NUTRITION_TARGET_NOT_FOUND) reporting no target exists yet for
    this user -- never synthesize or guess a value for this case."""


class NutritionTargetUnavailableError(Exception):
    """Raised when nutrition-calculation-service's target endpoint cannot
    be reached (circuit open, retries exhausted, timeout) or returns an
    unexpected non-success response -- a genuine service-health failure,
    distinct from NutritionTargetNotComputedYet above."""


class NutritionTargetPort(Protocol):
    async def get_target(
        self, authorization_header: str
    ) -> NutritionTargetResult | NutritionTargetNotComputedYet: ...
