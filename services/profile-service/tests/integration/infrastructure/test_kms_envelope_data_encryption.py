"""KmsEnvelopeDataEncryption: envelope-encryption round trip, per-user key
isolation, and resilience (circuit breaker, retry, timeout) per
resilience-patterns SKILL.md and test-plan section 2. Uses a fake KMS
client (no real AWS dependency) so timeouts/failures are simulated
explicitly, not relied on from a real slow dependency.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from cryptography.exceptions import InvalidTag
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.persistence.models import ProfileDataKeyModel
from infrastructure.security.kms_envelope_data_encryption import (
    KmsCallFailedError,
    KmsCircuitOpenError,
    KmsEnvelopeDataEncryption,
)

KMS_KEY_ID = "fake-kms-key-1"


class FakeKmsClient:
    """Synchronous fake matching boto3's KMS client method signatures --
    KmsEnvelopeDataEncryption always calls these via asyncio.to_thread."""

    WRAP_PREFIX = b"wrapped:"

    def __init__(self) -> None:
        self.mode = "normal"  # "normal" | "always_fail" | "slow"
        self.call_count = 0

    def generate_data_key(self, KeyId, KeySpec):
        self.call_count += 1
        self._maybe_misbehave()
        plaintext = uuid.uuid4().bytes + uuid.uuid4().bytes  # 32 bytes
        return dict(Plaintext=plaintext, CiphertextBlob=self.WRAP_PREFIX + plaintext)

    def decrypt(self, CiphertextBlob, KeyId):
        self.call_count += 1
        self._maybe_misbehave()
        assert CiphertextBlob.startswith(self.WRAP_PREFIX)
        return dict(Plaintext=CiphertextBlob[len(self.WRAP_PREFIX) :])

    def _maybe_misbehave(self) -> None:
        import time

        if self.mode == "always_fail":
            raise RuntimeError("Simulated KMS failure.")
        if self.mode == "slow":
            time.sleep(5)


@pytest.fixture
def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


async def test_encrypt_decrypt_round_trip_for_a_users_key(session_factory):
    adapter = KmsEnvelopeDataEncryption(session_factory, FakeKmsClient(), KMS_KEY_ID)
    user_id = uuid.uuid4()

    ciphertext = await adapter.encrypt(user_id, "70.5")
    plaintext = await adapter.decrypt(user_id, ciphertext)

    assert plaintext == "70.5"


async def test_two_different_users_ciphertexts_for_same_plaintext_differ(session_factory):
    adapter = KmsEnvelopeDataEncryption(session_factory, FakeKmsClient(), KMS_KEY_ID)
    user_a, user_b = uuid.uuid4(), uuid.uuid4()

    ciphertext_a = await adapter.encrypt(user_a, "70.5")
    ciphertext_b = await adapter.encrypt(user_b, "70.5")

    assert ciphertext_a != ciphertext_b


async def test_decrypt_with_a_different_users_key_fails(session_factory):
    adapter = KmsEnvelopeDataEncryption(session_factory, FakeKmsClient(), KMS_KEY_ID)
    user_a, user_b = uuid.uuid4(), uuid.uuid4()

    ciphertext_a = await adapter.encrypt(user_a, "70.5")
    # user_b has never encrypted anything, so it gets its OWN fresh DEK --
    # decrypting user_a's ciphertext under user_b's key must not succeed.
    with pytest.raises(InvalidTag):
        await adapter.decrypt(user_b, ciphertext_a)


async def test_circuit_opens_after_consecutive_failure_threshold(session_factory):
    kms_client = FakeKmsClient()
    kms_client.mode = "always_fail"
    adapter = KmsEnvelopeDataEncryption(
        session_factory, kms_client, KMS_KEY_ID, fail_max=3, reset_timeout_seconds=30
    )
    user_id = uuid.uuid4()

    # pybreaker counts the call that reaches fail_max as the one that trips
    # the breaker -- that Nth call itself surfaces as CircuitBreakerError
    # (-> KmsCircuitOpenError here), not the underlying failure. So
    # fail_max=3 means 2 "plain" failures, then the 3rd call already opens
    # the circuit.
    for _ in range(2):
        with pytest.raises(KmsCallFailedError):
            await adapter.encrypt(user_id, "70.5")

    with pytest.raises(KmsCircuitOpenError):
        await adapter.encrypt(user_id, "70.5")

    # Circuit is open -- calls fail fast without even reaching the fake
    # KMS client (no unbounded wait, no further attempt to call out).
    with pytest.raises(KmsCircuitOpenError):
        await adapter.encrypt(user_id, "70.5")


async def test_circuit_half_open_to_closed_after_reset_timeout(session_factory):
    kms_client = FakeKmsClient()
    kms_client.mode = "always_fail"
    adapter = KmsEnvelopeDataEncryption(
        session_factory, kms_client, KMS_KEY_ID, fail_max=2, reset_timeout_seconds=0
    )
    user_id = uuid.uuid4()

    # fail_max=2 -- the 1st call fails plainly, the 2nd already trips the
    # breaker (see the previous test's comment for pybreaker's exact
    # counting behavior).
    with pytest.raises(KmsCallFailedError):
        await adapter.encrypt(user_id, "70.5")
    with pytest.raises(KmsCircuitOpenError):
        await adapter.encrypt(user_id, "70.5")

    # reset_timeout_seconds=0 -- the breaker allows an immediate trial call.
    kms_client.mode = "normal"
    ciphertext = await adapter.encrypt(user_id, "70.5")
    assert ciphertext is not None


async def test_concurrent_first_use_dek_generation_for_same_new_user_stores_exactly_one_key(
    session_factory,
):
    """Two concurrent first-use requests for the same brand-new user_id
    both see no existing row (_load_wrapped_key returns None for both),
    both generate a DEK, and both race to insert into profile_data_keys --
    must converge on exactly one stored key (ON CONFLICT DO NOTHING +
    re-read-on-conflict), never two rows, never an unhandled IntegrityError,
    and never two callers silently using two different unwrapped DEKs."""
    user_id = uuid.uuid4()
    # Separate adapter instances (so their in-process DEK caches can't
    # short-circuit the race) wrapping separate fake KMS clients (so a
    # "lost the race" adapter that failed to re-read the winner's key
    # would produce a DIFFERENT, wrong plaintext DEK -- catching the bug).
    adapter_a = KmsEnvelopeDataEncryption(session_factory, FakeKmsClient(), KMS_KEY_ID)
    adapter_b = KmsEnvelopeDataEncryption(session_factory, FakeKmsClient(), KMS_KEY_ID)

    ciphertext_a, ciphertext_b = await asyncio.gather(
        adapter_a.encrypt(user_id, "70.5"),
        adapter_b.encrypt(user_id, "70.5"),
    )

    async with session_factory() as session:
        count = await session.scalar(
            select(func.count()).where(ProfileDataKeyModel.user_id == user_id)
        )
    assert count == 1  # exactly one key persisted despite two concurrent first-use inserts

    # Both adapters must have converged on the SAME underlying DEK -- each
    # can decrypt what the OTHER encrypted.
    assert await adapter_a.decrypt(user_id, ciphertext_b) == "70.5"
    assert await adapter_b.decrypt(user_id, ciphertext_a) == "70.5"


async def test_explicit_timeout_enforced_on_kms_call(session_factory):
    kms_client = FakeKmsClient()
    kms_client.mode = "slow"
    adapter = KmsEnvelopeDataEncryption(
        session_factory, kms_client, KMS_KEY_ID, call_timeout_seconds=0.2, fail_max=10
    )
    user_id = uuid.uuid4()

    with pytest.raises(KmsCallFailedError):
        await adapter.encrypt(user_id, "70.5")
