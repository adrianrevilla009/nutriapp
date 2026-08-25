"""goal_policy -- validates goal type/target combinations.

Rules pinned down in /plans/profile-service/test-plan.md section 0
(assumption, approved alongside the test plan):
  - target_date is required for LOSE/GAIN, optional (ignored if given) for
    MAINTAIN.
  - target_value is required for LOSE/GAIN, optional for MAINTAIN.
  - LOSE: target_value must be strictly less than the latest recorded
    weight, if one exists; skipped (accepted) if no weight recorded yet.
  - GAIN: target_value must be strictly greater than the latest recorded
    weight, same skip-if-absent rule.
  - target_date, when given, must be in the future -- already enforced by
    GoalTarget's own __post_init__, re-checked here defensively so a
    caller that bypasses GoalTarget construction still gets a policy
    error, not a silent acceptance.
  - No bound on the magnitude of target_value itself.
"""

from __future__ import annotations

from datetime import datetime, timezone

from domain.value_objects.goal_target import GoalTarget, InvalidGoalTargetError
from domain.value_objects.goal_type import GoalType


class MissingGoalTargetDateError(Exception):
    """Raised when target_date is missing for a LOSE/GAIN goal."""


def validate(
    goal_type: GoalType,
    goal_target: GoalTarget,
    latest_weight_kg: float | None,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(timezone.utc)

    if goal_type == GoalType.MAINTAIN:
        return

    if goal_target.target_date is None:
        raise MissingGoalTargetDateError(f"target_date is required for {goal_type.value} goals.")
    if goal_target.target_date <= now.date():
        raise InvalidGoalTargetError("target_date must be in the future.")

    if goal_target.target_value is None:
        raise InvalidGoalTargetError(f"target_value is required for {goal_type.value} goals.")

    if latest_weight_kg is None:
        return

    if goal_type == GoalType.LOSE and not (goal_target.target_value < latest_weight_kg):
        raise InvalidGoalTargetError(
            "target_value must be strictly less than the latest recorded weight for a LOSE goal."
        )
    if goal_type == GoalType.GAIN and not (goal_target.target_value > latest_weight_kg):
        raise InvalidGoalTargetError(
            "target_value must be strictly greater than the latest recorded weight for a GAIN goal."
        )
