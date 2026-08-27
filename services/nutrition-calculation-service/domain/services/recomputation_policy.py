"""Recomputation policy -- maps an inbound triggering event type to the
`reason` recorded on the outbound `NutritionValueRecomputed`/
`NutritionTargetUpdated` event (docs/events-catalog.md's documented
`reason` enums, implementation plan section 5). Kept as a pure mapping,
isolated from any messaging/consumer concern, so the reason vocabulary is
defined and tested in exactly one place.
"""

from __future__ import annotations

FORMULA_CORRECTION_REASON = "formula_correction"

_TOTAL_RECOMPUTE_REASON_BY_TRIGGER: dict[str, str] = {
    "FoodEntryLogged": "food_entry_logged",
    "FoodEntryCorrected": "food_entry_corrected",
    "FoodEntryDeleted": "food_entry_deleted",
}

_TARGET_RECOMPUTE_REASON_BY_TRIGGER: dict[str, str] = {
    "WeightRecorded": "weight_recorded",
    "BodyMetricRecorded": "body_metric_recorded",
    "GoalSet": "goal_set",
    "GoalUpdated": "goal_updated",
}


class UnrecognizedTriggerEventError(ValueError):
    """Raised when a consumer hands this policy an event type it does not
    recognize as a valid recompute trigger -- a bug in the consumer's own
    routing, not something to guess a reason for."""


def total_recompute_reason_for(trigger_event_type: str) -> str:
    try:
        return _TOTAL_RECOMPUTE_REASON_BY_TRIGGER[trigger_event_type]
    except KeyError as exc:
        raise UnrecognizedTriggerEventError(
            f"{trigger_event_type!r} is not a recognized nutrient-total recompute trigger."
        ) from exc


def target_recompute_reason_for(trigger_event_type: str) -> str:
    try:
        return _TARGET_RECOMPUTE_REASON_BY_TRIGGER[trigger_event_type]
    except KeyError as exc:
        raise UnrecognizedTriggerEventError(
            f"{trigger_event_type!r} is not a recognized nutrition-target recompute trigger."
        ) from exc
