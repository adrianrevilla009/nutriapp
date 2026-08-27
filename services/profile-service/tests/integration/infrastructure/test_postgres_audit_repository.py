"""Integration tests: PostgresAuditRepository against real (testcontainers)
Postgres, including proof that the append-only DB role is genuinely
enforced at the connection level, not just documented (implementation plan
Addendum 2, requirement 6; test-plan Addendum 2)."""

from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from domain.entities.audit_record import AuditRecord
from infrastructure.composition_root import AUDIT_WRITER_ROLE
from infrastructure.persistence.models import AuditLogModel
from infrastructure.persistence.postgres_audit_repository import PostgresAuditRepository


@pytest.fixture
async def session(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as s:
        yield s


@pytest.fixture
async def audit_writer_session(db_engine, postgres_async_url):
    """A session whose underlying connection is genuinely restricted to
    AUDIT_WRITER_ROLE via `SET ROLE` at connect time (the same mechanism
    Container.audit_engine uses in composition_root.py) -- proves the
    privilege separation is real at runtime, not just a grant nobody
    connects as."""
    async with db_engine.begin() as conn:
        current_user = (await conn.execute(text("SELECT current_user"))).scalar_one()
        await conn.execute(
            text(
                f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{AUDIT_WRITER_ROLE}') THEN
                        CREATE ROLE "{AUDIT_WRITER_ROLE}" NOLOGIN;
                    END IF;
                END
                $$;
                """
            )
        )
        await conn.execute(text(f'GRANT INSERT ON audit_records TO "{AUDIT_WRITER_ROLE}"'))
        await conn.execute(
            text(f'REVOKE UPDATE, DELETE ON audit_records FROM "{AUDIT_WRITER_ROLE}"')
        )
        await conn.execute(text(f'GRANT "{AUDIT_WRITER_ROLE}" TO "{current_user}"'))

    restricted_engine = create_async_engine(
        postgres_async_url,
        connect_args={"server_settings": {"role": AUDIT_WRITER_ROLE}},
    )
    async with AsyncSession(restricted_engine, expire_on_commit=False) as s:
        yield s
    await restricted_engine.dispose()


async def test_audit_repository__record__is_persisted_and_readable(session):
    repo = PostgresAuditRepository(session)
    entry = AuditRecord(
        action="biometric_snapshot_revealed",
        target_type="profile",
        target_id="user-123",
        outcome="success",
        correlation_id="corr-1",
        actor_id="nutrition-calculation-service",
        metadata={"fields": ["weight_kg"]},
    )
    await repo.record(entry)

    result = await session.execute(
        select(AuditLogModel).where(AuditLogModel.audit_id == entry.audit_id)
    )
    row = result.scalar_one()
    assert row.action == "biometric_snapshot_revealed"
    assert row.outcome == "success"
    assert row.audit_metadata == {"fields": ["weight_kg"]}


async def test_audit_repository__every_action_produces_a_record_on_both_outcomes(session):
    repo = PostgresAuditRepository(session)
    success = AuditRecord(
        action="biometric_snapshot_revealed",
        target_type="profile",
        target_id="u1",
        outcome="success",
        correlation_id="c1",
    )
    failure = AuditRecord(
        action="biometric_snapshot_revealed",
        target_type="profile",
        target_id="u1",
        outcome="failure",
        correlation_id="c2",
        metadata={"reason": "invalid_caller_credential"},
    )
    await repo.record(success)
    await repo.record(failure)

    result = await session.execute(select(AuditLogModel).where(AuditLogModel.target_id == "u1"))
    rows = result.scalars().all()
    outcomes = {row.outcome for row in rows}
    assert outcomes == {"success", "failure"}


async def test_audit_repository__connection_actually_restricted_to_audit_writer_role__insert_succeeds(
    audit_writer_session, session
):
    repo = PostgresAuditRepository(audit_writer_session)
    entry = AuditRecord(
        action="biometric_snapshot_revealed",
        target_type="profile",
        target_id="u-role-check",
        outcome="success",
        correlation_id="c-role-check",
    )
    await repo.record(entry)  # must not raise -- INSERT is granted

    # Read back via the unrestricted `session`, not `audit_writer_session`:
    # the role is deliberately INSERT-only, so it cannot SELECT its own
    # rows back either.
    result = await session.execute(
        select(AuditLogModel).where(AuditLogModel.target_id == "u-role-check")
    )
    assert result.scalar_one().outcome == "success"


async def test_audit_repository__connection_actually_restricted_to_audit_writer_role__update_is_denied(
    audit_writer_session, session
):
    # Seed a row via the unrestricted session (the repository under test is
    # never used to write here -- this only proves the *connection*
    # AUDIT_WRITER_ROLE resolves to cannot UPDATE, independent of the
    # repository's own code path).
    repo = PostgresAuditRepository(session)
    entry = AuditRecord(
        action="biometric_snapshot_revealed",
        target_type="profile",
        target_id="u-update-check",
        outcome="failure",
        correlation_id="c-update-check",
    )
    await repo.record(entry)

    stmt = text("UPDATE audit_records SET outcome = 'success' WHERE target_id = 'u-update-check'")
    with pytest.raises(DBAPIError, match="permission denied"):
        await audit_writer_session.execute(stmt)


async def test_audit_repository__connection_actually_restricted_to_audit_writer_role__delete_is_denied(
    audit_writer_session, session
):
    repo = PostgresAuditRepository(session)
    entry = AuditRecord(
        action="biometric_snapshot_revealed",
        target_type="profile",
        target_id="u-delete-check",
        outcome="failure",
        correlation_id="c-delete-check",
    )
    await repo.record(entry)

    stmt = text("DELETE FROM audit_records WHERE target_id = 'u-delete-check'")
    with pytest.raises(DBAPIError, match="permission denied"):
        await audit_writer_session.execute(stmt)
