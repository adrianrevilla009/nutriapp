from __future__ import annotations

import uuid

import pytest

from application.errors import ProfileNotFoundError
from application.queries.get_profile_snapshot import (
    GetProfileSnapshotHandler,
    GetProfileSnapshotQuery,
)
from tests.fixtures.factories import FakeDataEncryption, FakeSnapshotProjector


async def test_existing_profile_returns_decrypted_snapshot_dto():
    snapshot = FakeSnapshotProjector()
    encryption = FakeDataEncryption()
    user_id = uuid.uuid4()
    snapshot.rows[user_id] = dict(
        user_id=user_id,
        consent_granted=True,
        weight_kg=await encryption.encrypt(user_id, "70.0"),
        height_cm=None,
        age=None,
        sex=None,
        activity_level=None,
        goal_type="LOSE",
        goal_target_value=await encryption.encrypt(user_id, "65.0"),
        goal_target_date="2026-12-01",
    )

    handler = GetProfileSnapshotHandler(snapshot, encryption)
    dto = await handler.handle(GetProfileSnapshotQuery(user_id=user_id))

    assert dto.weight_kg == 70.0
    assert dto.goal_target_value == 65.0
    assert dto.goal_type == "LOSE"


async def test_unknown_user_id_raises_not_found():
    handler = GetProfileSnapshotHandler(FakeSnapshotProjector(), FakeDataEncryption())
    query = GetProfileSnapshotQuery(user_id=uuid.uuid4())
    with pytest.raises(ProfileNotFoundError):
        await handler.handle(query)
