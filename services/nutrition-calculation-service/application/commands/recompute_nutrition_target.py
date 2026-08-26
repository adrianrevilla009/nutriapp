"""RecomputeNutritionTargetCommand -- triggered by
`RabbitMqProfileMetricsConsumer` on `WeightRecorded`/`BodyMetricRecorded`/
`GoalSet`/`GoalUpdated` (implementation plan section 1, acceptance
criterion 3 / Addendum 1). Calls `ProfileRevealPort` for plaintext metrics,
then the pure domain calculators, then persists + publishes.

Never guesses or defaults a biometric value (implementation plan Addendum
1's security sub-addendum, requirement 7): if the reveal call fails/the
circuit is open, or the user's `Sex.OTHER` has no explicit calculation-
constant selection available, the recompute is deferred cleanly --
`RecomputeNutritionTargetDeferredError` is raised for the consumer to catch,
log, and return without producing a `NutritionTargetUpdated` event.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from domain.entities.nutrition_target import NutritionTarget
from domain.events.nutrition_target_updated import build_nutrition_target_updated_event
from domain.ports.nutrition_target_repository_port import NutritionTargetRepositoryPort
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.ports.profile_reveal_port import ProfileRevealPort, ProfileRevealUnavailableError
from domain.ports.target_history_repository_port import TargetHistoryRepositoryPort
from domain.ports.user_metrics_snapshot_port import (
    UserMetricsSnapshotMetadata,
    UserMetricsSnapshotPort,
)
from domain.services.bmr_calculator import InvalidBiometricInputError, calculate_bmr
from domain.services.calorie_target_calculator import calculate_calorie_target
from domain.services.macro_repartition_calculator import calculate_macro_repartition
from domain.services.recomputation_policy import target_recompute_reason_for
from domain.services.tdee_calculator import calculate_tdee
from domain.value_objects.formula_version import CURRENT_FORMULA_VERSION
from domain.value_objects.sex import CalculationSexConstant


class RecomputeNutritionTargetDeferredError(Exception):
    """Raised when the recompute cannot be safely completed this attempt --
    caught by the consumer, logged, and left for the next triggering event
    (never a crash, never a silently-defaulted biometric input)."""


@dataclass(frozen=True, slots=True)
class RecomputeNutritionTargetCommand:
    user_id: uuid.UUID
    trigger_event_type: str
    correlation_id: str
    goal_adjustment_kcal: float = 0.0
    calculation_sex_constant_override: CalculationSexConstant | None = None


class RecomputeNutritionTargetHandler:
    def __init__(
        self,
        profile_reveal_port: ProfileRevealPort,
        target_repository: NutritionTargetRepositoryPort,
        history_repository: TargetHistoryRepositoryPort,
        snapshot_port: UserMetricsSnapshotPort,
        outbox_repository: OutboxRepositoryPort,
    ) -> None:
        self._profile_reveal_port = profile_reveal_port
        self._target_repository = target_repository
        self._history_repository = history_repository
        self._snapshot_port = snapshot_port
        self._outbox_repository = outbox_repository

    async def handle(self, command: RecomputeNutritionTargetCommand) -> NutritionTarget:
        try:
            metrics = await self._profile_reveal_port.reveal(command.user_id)
        except ProfileRevealUnavailableError as exc:
            raise RecomputeNutritionTargetDeferredError(
                f"Deferring nutrition target recompute for user {command.user_id}: "
                "profile-service metrics unavailable (circuit open, retries exhausted, "
                "or no recorded metrics)."
            ) from exc

        try:
            bmr_result = calculate_bmr(
                weight_kg=metrics.weight_kg,
                height_cm=metrics.height_cm,
                age=metrics.age,
                sex=metrics.sex,
                calculation_sex_constant=command.calculation_sex_constant_override,
            )
        except InvalidBiometricInputError as exc:
            raise RecomputeNutritionTargetDeferredError(
                f"Deferring nutrition target recompute for user {command.user_id}: {exc}"
            ) from exc

        tdee_kcal = calculate_tdee(
            bmr_kcal=bmr_result.bmr_kcal, activity_level=metrics.activity_level
        )
        calorie_result = calculate_calorie_target(
            bmr_kcal=bmr_result.bmr_kcal,
            tdee_kcal=tdee_kcal,
            goal_type=metrics.goal_type,
            goal_adjustment_kcal=command.goal_adjustment_kcal,
        )
        macro_targets = calculate_macro_repartition(
            calorie_target_kcal=calorie_result.calorie_target_kcal, weight_kg=metrics.weight_kg
        )

        now = datetime.now(timezone.utc)
        reason = target_recompute_reason_for(command.trigger_event_type)
        target = NutritionTarget(
            user_id=command.user_id,
            bmr_kcal=bmr_result.bmr_kcal,
            tdee_kcal=tdee_kcal,
            calorie_target_kcal=calorie_result.calorie_target_kcal,
            macro_targets=macro_targets,
            goal_type=metrics.goal_type,
            activity_level=metrics.activity_level,
            sex_constant_used=bmr_result.sex_constant_used,
            clamped=calorie_result.clamped,
            clamp_reason=calorie_result.clamp_reason,
            formula_version=CURRENT_FORMULA_VERSION,
            reason=reason,
            effective_from=now,
        )

        await self._target_repository.upsert(target)
        await self._history_repository.append(target)
        await self._snapshot_port.record_fetch(
            UserMetricsSnapshotMetadata(
                user_id=command.user_id,
                last_fetched_at=now,
                formula_version=CURRENT_FORMULA_VERSION,
                sex_constant_used=bmr_result.sex_constant_used.value,
            )
        )

        event = build_nutrition_target_updated_event(
            user_id=command.user_id,
            bmr_kcal=target.bmr_kcal,
            tdee_kcal=target.tdee_kcal,
            calorie_target_kcal=target.calorie_target_kcal,
            macro_targets=target.macro_targets,
            goal_type=target.goal_type,
            activity_level=target.activity_level,
            clamped=target.clamped,
            clamp_reason=target.clamp_reason,
            formula_version=target.formula_version,
            reason=reason,  # type: ignore[arg-type]
            effective_from=now,
            correlation_id=command.correlation_id,
        )
        await self._outbox_repository.enqueue(event)
        return target
