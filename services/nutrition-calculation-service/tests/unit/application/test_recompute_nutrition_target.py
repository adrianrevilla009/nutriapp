from __future__ import annotations

import uuid

import pytest

from application.commands.recompute_nutrition_target import (
    RecomputeNutritionTargetCommand,
    RecomputeNutritionTargetDeferredError,
    RecomputeNutritionTargetHandler,
)
from domain.value_objects.activity_level import ActivityLevel
from domain.value_objects.goal_type import GoalType
from domain.value_objects.sex import CalculationSexConstant, Sex
from tests.fixtures.factories import (
    FakeNutritionTargetRepository,
    FakeOutboxRepository,
    FakeProfileRevealPort,
    FakeTargetHistoryRepository,
    FakeUserMetricsSnapshotRepository,
    default_revealed_metrics,
)

USER_ID = uuid.uuid4()


def _build_handler(profile_reveal_port):
    target_repo = FakeNutritionTargetRepository()
    history_repo = FakeTargetHistoryRepository()
    snapshot_repo = FakeUserMetricsSnapshotRepository()
    outbox = FakeOutboxRepository()
    handler = RecomputeNutritionTargetHandler(
        profile_reveal_port, target_repo, history_repo, snapshot_repo, outbox
    )
    return handler, target_repo, history_repo, snapshot_repo, outbox


async def test_successful_recompute_persists_target_history_snapshot_and_publishes_event():
    reveal_port = FakeProfileRevealPort()
    handler, target_repo, history_repo, snapshot_repo, outbox = _build_handler(reveal_port)

    command = RecomputeNutritionTargetCommand(
        user_id=USER_ID, trigger_event_type="WeightRecorded", correlation_id="corr-1"
    )
    target = await handler.handle(command)

    assert reveal_port.call_count == 1
    assert (await target_repo.get_current(USER_ID)) == target
    assert len(history_repo.appended) == 1
    snapshot = await snapshot_repo.get(USER_ID)
    assert snapshot is not None
    assert snapshot.sex_constant_used == "MALE"
    assert len(outbox.enqueued) == 1
    assert outbox.enqueued[0].event_type == "NutritionTargetUpdated"
    assert outbox.enqueued[0].payload["reason"] == "weight_recorded"

    # Security guarantee: nothing about the fake's plaintext metrics object
    # itself is ever persisted -- only derived scalars and metadata.
    assert not hasattr(snapshot, "weight_kg")


async def test_reveal_unavailable_defers_and_does_not_publish():
    reveal_port = FakeProfileRevealPort(should_fail=True)
    handler, target_repo, history_repo, _snapshot_repo, outbox = _build_handler(reveal_port)

    command = RecomputeNutritionTargetCommand(
        user_id=USER_ID, trigger_event_type="GoalSet", correlation_id="corr-1"
    )
    with pytest.raises(RecomputeNutritionTargetDeferredError):
        await handler.handle(command)

    assert await target_repo.get_current(USER_ID) is None
    assert history_repo.appended == []
    assert outbox.enqueued == []


async def test_sex_other_without_override_defers_cleanly():
    reveal_port = FakeProfileRevealPort(metrics=default_revealed_metrics(sex=Sex.OTHER))
    handler, target_repo, _history_repo, _snapshot_repo, outbox = _build_handler(reveal_port)

    command = RecomputeNutritionTargetCommand(
        user_id=USER_ID, trigger_event_type="BodyMetricRecorded", correlation_id="corr-1"
    )
    with pytest.raises(RecomputeNutritionTargetDeferredError):
        await handler.handle(command)

    assert await target_repo.get_current(USER_ID) is None
    assert outbox.enqueued == []


async def test_sex_other_with_override_computes_successfully():
    reveal_port = FakeProfileRevealPort(metrics=default_revealed_metrics(sex=Sex.OTHER))
    handler, target_repo, _history_repo, snapshot_repo, _outbox = _build_handler(reveal_port)

    command = RecomputeNutritionTargetCommand(
        user_id=USER_ID,
        trigger_event_type="BodyMetricRecorded",
        correlation_id="corr-1",
        calculation_sex_constant_override=CalculationSexConstant.FEMALE,
    )
    target = await handler.handle(command)

    assert target.sex_constant_used is CalculationSexConstant.FEMALE
    snapshot = await snapshot_repo.get(USER_ID)
    assert snapshot.sex_constant_used == "FEMALE"


async def test_replaying_same_trigger_does_not_double_call_reveal_when_deduped():
    """Idempotency at the application layer: this handler itself has no
    dedup logic (that lives at the consumer/ProcessedEventsPort layer,
    integration-tested in test_profile_metrics_consumer.py) -- this test
    documents that two independent commands both call reveal() once each,
    i.e. dedup must happen one layer up, never silently inside the domain
    calculation itself."""
    reveal_port = FakeProfileRevealPort()
    handler, *_ = _build_handler(reveal_port)

    command = RecomputeNutritionTargetCommand(
        user_id=USER_ID, trigger_event_type="GoalUpdated", correlation_id="corr-1"
    )
    await handler.handle(command)
    await handler.handle(command)

    assert reveal_port.call_count == 2


async def test_activity_level_and_goal_type_flow_through_from_reveal():
    reveal_port = FakeProfileRevealPort(
        metrics=default_revealed_metrics(
            activity_level=ActivityLevel.ACTIVE, goal_type=GoalType.LOSE
        )
    )
    handler, *_ = _build_handler(reveal_port)

    command = RecomputeNutritionTargetCommand(
        user_id=USER_ID, trigger_event_type="GoalUpdated", correlation_id="corr-1"
    )
    target = await handler.handle(command)

    assert target.activity_level is ActivityLevel.ACTIVE
    assert target.goal_type is GoalType.LOSE
