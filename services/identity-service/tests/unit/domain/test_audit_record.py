import pytest

from domain.entities.audit_record import AuditRecord, UnsafeAuditMetadataError


def test_audit_record__forbidden_metadata_key__raises_unsafe_audit_metadata_error():
    with pytest.raises(UnsafeAuditMetadataError):
        AuditRecord(
            action="login",
            target_type="user",
            target_id="123",
            outcome="failure",
            correlation_id="corr-1",
            metadata={"password": "should-never-be-here"},
        )


def test_audit_record__valid_metadata__is_accepted():
    record = AuditRecord(
        action="login",
        target_type="user",
        target_id="123",
        outcome="success",
        correlation_id="corr-1",
        metadata={"reason": "ok"},
    )
    assert record.outcome == "success"
