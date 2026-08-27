"""Unit tests for GetBiometricSnapshotForCalculationHandler (implementation
plan Addendum 2, fake ports only -- hexagonal-architecture SKILL.md)."""

from __future__ import annotations

import uuid

import pytest

from application.errors import (
    InvalidCallerCredentialError,
    ProfileNotFoundError,
    RevealRateLimitedError,
)
from application.queries.get_biometric_snapshot_for_calculation import (
    REVEALED_FIELDS,
    GetBiometricSnapshotForCalculationHandler,
    GetBiometricSnapshotForCalculationQuery,
)
from domain.ports.rate_limiter_port import RateLimiterUnavailableError
from tests.fixtures.factories import (
    FakeAuditRepository,
    FakeDataEncryption,
    FakeRateLimiter,
    FakeSnapshotProjector,
)

VALID_CREDENTIAL = "the-nutrition-calc-credential"
CALLER_CREDENTIALS = {VALID_CREDENTIAL: "nutrition-calculation-service"}


async def _seed_full_snapshot(
    snapshot: FakeSnapshotProjector, encryption: FakeDataEncryption, user_id
):
    snapshot.rows[user_id] = dict(
        user_id=user_id,
        consent_granted=True,
        weight_kg=await encryption.encrypt(user_id, "82.5"),
        height_cm=await encryption.encrypt(user_id, "180.0"),
        age=await encryption.encrypt(user_id, "34"),
        sex=await encryption.encrypt(user_id, "MALE"),
        activity_level=await encryption.encrypt(user_id, "MODERATE"),
        goal_type="LOSE",
        goal_target_value=await encryption.encrypt(user_id, "75.0"),
        goal_target_date="2027-01-01",
    )


def _make_handler(snapshot=None, encryption=None, audit=None, rate_limiter=None, **kwargs):
    return GetBiometricSnapshotForCalculationHandler(
        snapshot or FakeSnapshotProjector(),
        encryption or FakeDataEncryption(),
        audit or FakeAuditRepository(),
        rate_limiter or FakeRateLimiter(),
        CALLER_CREDENTIALS,
        **kwargs,
    )


async def test_response_contains_exactly_the_six_allow_listed_fields_and_nothing_else():
    snapshot = FakeSnapshotProjector()
    encryption = FakeDataEncryption()
    user_id = uuid.uuid4()
    await _seed_full_snapshot(snapshot, encryption, user_id)
    handler = _make_handler(snapshot=snapshot, encryption=encryption)

    dto = await handler.handle(
        GetBiometricSnapshotForCalculationQuery(
            user_id=user_id, caller_service_credential=VALID_CREDENTIAL, correlation_id="corr-1"
        )
    )

    dto_fields = {f.name for f in dto.__dataclass_fields__.values()}
    assert dto_fields == set(REVEALED_FIELDS)
    assert dto.weight_kg == 82.5
    assert dto.height_cm == 180.0
    assert dto.age == 34
    assert dto.sex == "MALE"
    assert dto.activity_level == "MODERATE"
    assert dto.goal_type == "LOSE"
    # Never exposed by this endpoint, even though the read model has them.
    assert not hasattr(dto, "goal_target_value")
    assert not hasattr(dto, "goal_target_date")
    assert not hasattr(dto, "consent_granted")


async def test_success_writes_exactly_one_audit_record_with_field_names_only():
    snapshot = FakeSnapshotProjector()
    encryption = FakeDataEncryption()
    audit = FakeAuditRepository()
    user_id = uuid.uuid4()
    await _seed_full_snapshot(snapshot, encryption, user_id)
    handler = _make_handler(snapshot=snapshot, encryption=encryption, audit=audit)

    await handler.handle(
        GetBiometricSnapshotForCalculationQuery(
            user_id=user_id, caller_service_credential=VALID_CREDENTIAL, correlation_id="corr-1"
        )
    )

    assert len(audit.records) == 1
    record = audit.records[0]
    assert record.outcome == "success"
    assert record.action == "biometric_snapshot_revealed"
    assert record.target_type == "profile"
    assert record.target_id == str(user_id)
    assert record.actor_id == "nutrition-calculation-service"
    assert record.correlation_id == "corr-1"
    assert set(record.metadata["fields"]) == set(REVEALED_FIELDS)
    # No numeric/enum VALUE anywhere in the audit metadata.
    for value in record.metadata.values():
        assert value != 82.5
        assert value != "MALE"


async def test_wrong_credential_rejected_with_one_failure_audit_record_and_no_data_returned():
    snapshot = FakeSnapshotProjector()
    encryption = FakeDataEncryption()
    audit = FakeAuditRepository()
    user_id = uuid.uuid4()
    await _seed_full_snapshot(snapshot, encryption, user_id)
    handler = _make_handler(snapshot=snapshot, encryption=encryption, audit=audit)

    query = GetBiometricSnapshotForCalculationQuery(
        user_id=user_id, caller_service_credential="wrong", correlation_id="corr-2"
    )
    with pytest.raises(InvalidCallerCredentialError):
        await handler.handle(query)

    assert len(audit.records) == 1
    record = audit.records[0]
    assert record.outcome == "failure"
    assert record.actor_id is None
    assert record.metadata == {"reason": "invalid_caller_credential"}
    # Never decrypts on a rejected-credential call.
    assert encryption.decrypt_calls == []


async def test_missing_credential_rejected():
    handler = _make_handler()
    user_id = uuid.uuid4()
    query = GetBiometricSnapshotForCalculationQuery(
        user_id=user_id, caller_service_credential="", correlation_id="corr-3"
    )
    with pytest.raises(InvalidCallerCredentialError):
        await handler.handle(query)


async def test_rate_limit_exceeded_raises_and_never_invokes_the_encryption_port():
    snapshot = FakeSnapshotProjector()
    encryption = FakeDataEncryption()
    audit = FakeAuditRepository()
    rate_limiter = FakeRateLimiter()
    user_id = uuid.uuid4()
    await _seed_full_snapshot(snapshot, encryption, user_id)
    handler = _make_handler(
        snapshot=snapshot, encryption=encryption, audit=audit, rate_limiter=rate_limiter
    )
    query = GetBiometricSnapshotForCalculationQuery(
        user_id=user_id, caller_service_credential=VALID_CREDENTIAL, correlation_id="corr-4"
    )
    # Pre-block the exact key this query will construct.
    rate_limiter.blocked_keys.add(handler._rate_limit_key(query))

    with pytest.raises(RevealRateLimitedError):
        await handler.handle(query)

    assert encryption.decrypt_calls == [], (
        "KMS-decrypting port must never be invoked once throttled"
    )
    assert len(audit.records) == 1
    record = audit.records[0]
    assert record.outcome == "failure"
    assert record.actor_id == "nutrition-calculation-service"
    assert record.metadata == {"reason": "rate_limited"}


async def test_rate_limiter_unavailable_propagates_and_never_invokes_the_encryption_port():
    snapshot = FakeSnapshotProjector()
    encryption = FakeDataEncryption()
    rate_limiter = FakeRateLimiter()
    rate_limiter.unavailable = True
    user_id = uuid.uuid4()
    await _seed_full_snapshot(snapshot, encryption, user_id)
    handler = _make_handler(snapshot=snapshot, encryption=encryption, rate_limiter=rate_limiter)

    query = GetBiometricSnapshotForCalculationQuery(
        user_id=user_id, caller_service_credential=VALID_CREDENTIAL, correlation_id="corr-5"
    )
    with pytest.raises(RateLimiterUnavailableError):
        await handler.handle(query)
    assert encryption.decrypt_calls == []


async def test_unknown_profile_raises_not_found_and_writes_failure_audit_record():
    audit = FakeAuditRepository()
    handler = _make_handler(audit=audit)
    user_id = uuid.uuid4()

    query = GetBiometricSnapshotForCalculationQuery(
        user_id=user_id, caller_service_credential=VALID_CREDENTIAL, correlation_id="corr-6"
    )
    with pytest.raises(ProfileNotFoundError):
        await handler.handle(query)

    assert len(audit.records) == 1
    assert audit.records[0].outcome == "failure"
    assert audit.records[0].metadata == {"reason": "profile_not_found"}


async def test_partially_populated_snapshot_returns_none_for_unset_fields():
    snapshot = FakeSnapshotProjector()
    encryption = FakeDataEncryption()
    user_id = uuid.uuid4()
    snapshot.rows[user_id] = dict(
        user_id=user_id,
        consent_granted=True,
        weight_kg=await encryption.encrypt(user_id, "60.0"),
        height_cm=None,
        age=None,
        sex=None,
        activity_level=None,
        goal_type=None,
        goal_target_value=None,
        goal_target_date=None,
    )
    handler = _make_handler(snapshot=snapshot, encryption=encryption)

    dto = await handler.handle(
        GetBiometricSnapshotForCalculationQuery(
            user_id=user_id, caller_service_credential=VALID_CREDENTIAL, correlation_id="corr-7"
        )
    )

    assert dto.weight_kg == 60.0
    assert dto.height_cm is None
    assert dto.age is None
    assert dto.sex is None
    assert dto.activity_level is None
    assert dto.goal_type is None


async def test_rate_limit_key_is_keyed_by_hashed_credential_and_user_id_not_raw_credential():
    handler = _make_handler()
    user_id = uuid.uuid4()
    query = GetBiometricSnapshotForCalculationQuery(
        user_id=user_id, caller_service_credential=VALID_CREDENTIAL, correlation_id="corr-8"
    )
    key = handler._rate_limit_key(query)
    assert VALID_CREDENTIAL not in key
    assert str(user_id) in key
