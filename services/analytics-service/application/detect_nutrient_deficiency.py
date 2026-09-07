"""Shared helper `HandleNutritionValueRecomputedHandler` calls once per
tracked nutrient after upserting that day's `micronutrient_window` row --
NOT a command in its own right (no HTTP route, no event consumes it
directly), so it lives alongside `entitlement_check.py` rather than under
`commands/` (same "shared cross-handler helper, not a port, not a
command" convention social-service's own `entitlement_check.py` uses).

Applies the domain's pure `evaluate_breach` result against the 14-day
cooldown recorded in `anomaly_alerts` (implementation plan section 9
addendum, resolution 2) -- publishes `NutrientDeficiencyDetected` via
Outbox only on a genuine breach outside the cooldown window."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from domain.events.nutrient_deficiency_detected import build_nutrient_deficiency_detected_event
from domain.ports.anomaly_alerts_repository_port import AnomalyAlertsRepositoryPort
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.services import anomaly_detector
from domain.value_objects.deficiency_signal import DeficiencySignal
from domain.value_objects.trend_point import TrendPoint

COOLDOWN = timedelta(days=14)


async def detect_and_record_deficiency(
    user_id: uuid.UUID,
    nutrient: str,
    recent_points: list[TrendPoint],
    target_min: float | None,
    anomaly_alerts: AnomalyAlertsRepositoryPort,
    outbox: OutboxRepositoryPort,
    correlation_id: str,
    now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> None:
    evaluation = anomaly_detector.evaluate_breach(recent_points, target_min)
    if not evaluation.breach:
        return

    now = now_fn()
    last_detected_at = await anomaly_alerts.most_recent_detection_at(user_id, nutrient)
    if last_detected_at is not None and (now - last_detected_at) < COOLDOWN:
        return

    most_recent_value = max(recent_points, key=lambda p: p.on_date).value
    # target_min is guaranteed non-None here: evaluate_breach() only ever
    # returns breach=True when target_min was not None (see
    # domain/services/anomaly_detector.py's excluded_no_target branch).
    assert target_min is not None
    signal = DeficiencySignal(
        nutrient=nutrient,
        value=most_recent_value,
        target_min=target_min,
        window_days=evaluation.window_days,
        sample_size=evaluation.sample_size,
    )
    await anomaly_alerts.record_detection(
        user_id=user_id,
        signal=nutrient,
        window_days=evaluation.window_days,
        value=most_recent_value,
        detected_at=now,
    )
    await outbox.enqueue(
        build_nutrient_deficiency_detected_event(
            user_id=user_id, signal=signal, detected_at=now, correlation_id=correlation_id
        )
    )
