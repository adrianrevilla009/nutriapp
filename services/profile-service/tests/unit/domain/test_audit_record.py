from __future__ import annotations

import pytest

from domain.entities.audit_record import AuditRecord, UnsafeAuditMetadataError


def test_valid_success_record_with_field_names_only():
    record = AuditRecord(
        action="biometric_snapshot_revealed",
        target_type="profile",
        target_id="user-1",
        outcome="success",
        correlation_id="corr-1",
        actor_id="nutrition-calculation-service",
        metadata={"fields": ["weight_kg", "height_cm"]},
    )
    assert record.outcome == "success"
    assert record.metadata == {"fields": ["weight_kg", "height_cm"]}


def test_valid_failure_record_with_reason_only():
    record = AuditRecord(
        action="biometric_snapshot_revealed",
        target_type="profile",
        target_id="user-1",
        outcome="failure",
        correlation_id="corr-1",
        metadata={"reason": "invalid_caller_credential"},
    )
    assert record.outcome == "failure"
    assert record.actor_id is None


@pytest.mark.parametrize("outcome", ["pending", "SUCCESS", "", "ok"])
def test_invalid_outcome_rejected(outcome):
    with pytest.raises(ValueError):
        AuditRecord(
            action="a",
            target_type="t",
            target_id="1",
            outcome=outcome,
            correlation_id="c",
        )


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "weight_kg",
        "height_cm",
        "age",
        "sex",
        "activity_level",
        "goal_type",
        "value",
        "target_value",
    ],
)
def test_metadata_containing_a_biometric_value_key_is_rejected(forbidden_key):
    with pytest.raises(UnsafeAuditMetadataError):
        AuditRecord(
            action="a",
            target_type="t",
            target_id="1",
            outcome="success",
            correlation_id="c",
            metadata={forbidden_key: 70.0},
        )


def test_default_metadata_is_empty_and_audit_id_and_occurred_at_are_generated():
    record = AuditRecord(
        action="a", target_type="t", target_id="1", outcome="success", correlation_id="c"
    )
    assert record.metadata == {}
    assert record.audit_id is not None
    assert record.occurred_at is not None
