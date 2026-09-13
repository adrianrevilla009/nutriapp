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


async def test_published_event_merges_real_micronutrient_minimums_for_an_adult_user():
    """Phase 2 (dri-rda-addendum.md): the outbox event's
    `nutrient_targets_min` carries calcium_mg/iron_mg/vitamin_c_mg
    alongside protein_g/fat_g for a 25-year-old male, using the exact
    figures cited in `domain/reference_data/dri_reference_table.py`."""
    reveal_port = FakeProfileRevealPort(
        metrics=default_revealed_metrics(age=25, sex=Sex.MALE)
    )
    handler, *_, outbox = _build_handler(reveal_port)

    command = RecomputeNutritionTargetCommand(
        user_id=USER_ID, trigger_event_type="WeightRecorded", correlation_id="corr-1"
    )
    await handler.handle(command)

    nutrient_targets_min = outbox.enqueued[0].payload["nutrient_targets_min"]
    assert nutrient_targets_min["calcium_mg"] == 1000.0
    assert nutrient_targets_min["iron_mg"] == 8.0
    assert nutrient_targets_min["vitamin_c_mg"] == 90.0
    assert "protein_g" in nutrient_targets_min
    assert "fat_g" in nutrient_targets_min


async def test_published_event_has_no_micronutrient_minimums_for_an_under_19_user():
    """Under-19 users get zero micronutrient entries -- absent, not
    defaulted (addendum acceptance criterion 4) -- while protein_g/fat_g
    (macro-derived, unaffected by this pass) are still present."""
    reveal_port = FakeProfileRevealPort(metrics=default_revealed_metrics(age=17))
    handler, *_, outbox = _build_handler(reveal_port)

    command = RecomputeNutritionTargetCommand(
        user_id=USER_ID, trigger_event_type="WeightRecorded", correlation_id="corr-1"
    )
    await handler.handle(command)

    nutrient_targets_min = outbox.enqueued[0].payload["nutrient_targets_min"]
    assert set(nutrient_targets_min.keys()) == {"protein_g", "fat_g"}
    for micronutrient in ("calcium_mg", "iron_mg", "vitamin_c_mg"):
        assert micronutrient not in nutrient_targets_min


async def test_sex_other_with_override_also_gets_micronutrient_minimums_for_the_selected_constant():
    reveal_port = FakeProfileRevealPort(
        metrics=default_revealed_metrics(sex=Sex.OTHER, age=40)
    )
    handler, *_, outbox = _build_handler(reveal_port)

    command = RecomputeNutritionTargetCommand(
        user_id=USER_ID,
        trigger_event_type="BodyMetricRecorded",
        correlation_id="corr-1",
        calculation_sex_constant_override=CalculationSexConstant.FEMALE,
    )
    await handler.handle(command)

    nutrient_targets_min = outbox.enqueued[0].payload["nutrient_targets_min"]
    assert nutrient_targets_min["iron_mg"] == 18.0


async def test_replaying_the_same_command_twice_produces_stable_identical_micronutrient_minimums():
    """Idempotency of the new keys specifically: two independent handler
    invocations for the same unchanged inputs must publish the exact same
    `nutrient_targets_min` micronutrient entries both times -- no drift, no
    double-application (test-plan reference, addendum section 8)."""
    reveal_port = FakeProfileRevealPort(metrics=default_revealed_metrics(age=60, sex=Sex.FEMALE))
    handler, *_, outbox = _build_handler(reveal_port)

    command = RecomputeNutritionTargetCommand(
        user_id=USER_ID, trigger_event_type="GoalUpdated", correlation_id="corr-1"
    )
    await handler.handle(command)
    await handler.handle(command)

    first, second = outbox.enqueued[0], outbox.enqueued[1]
    assert first.payload["nutrient_targets_min"] == second.payload["nutrient_targets_min"]
    assert first.payload["nutrient_targets_min"]["calcium_mg"] == 1200.0
    assert first.payload["nutrient_targets_min"]["iron_mg"] == 8.0
