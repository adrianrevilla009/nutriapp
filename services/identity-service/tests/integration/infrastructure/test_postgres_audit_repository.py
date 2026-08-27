import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from domain.entities.audit_record import AuditRecord
from infrastructure.composition_root import AUDIT_WRITER_ROLE
from infrastructure.persistence.models import AuditLogModel
from infrastructure.persistence.postgres_audit_repository import PostgresAuditRepository


@pytest.fixture()
async def session(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as s:
        yield s


@pytest.fixture()
async def audit_writer_session(db_engine, postgres_async_url):
    """A session whose underlying connection is genuinely restricted to
    AUDIT_WRITER_ROLE via `SET ROLE` at connect time (the same mechanism
    Container.audit_engine uses in composition_root.py) — proves the
    privilege separation is real at runtime, not just a grant nobody
    connects as (the exact gap /implementation-review flagged)."""
    async with db_engine.begin() as conn:
        current_user = (await conn.execute(text("SELECT current_user"))).scalar_one()
        # The Postgres role is a cluster-wide object that outlives any one
        # test's per-database schema (db_engine's create_all/drop_all only
        # touches tables) — the underlying container is session-scoped, so
        # this must be idempotent across every test that uses this fixture.
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
        await conn.execute(text("GRANT INSERT ON audit_log TO " + AUDIT_WRITER_ROLE))
        await conn.execute(text("REVOKE UPDATE, DELETE ON audit_log FROM " + AUDIT_WRITER_ROLE))
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
        action="login",
        target_type="user",
        target_id="user-123",
        outcome="success",
        correlation_id="corr-1",
        actor_id="user-123",
    )
    await repo.record(entry)

    result = await session.execute(
        select(AuditLogModel).where(AuditLogModel.audit_id == entry.audit_id)
    )
    row = result.scalar_one()
    assert row.action == "login"
    assert row.outcome == "success"


async def test_audit_repository__every_action_produces_a_record_on_both_outcomes(session):
    repo = PostgresAuditRepository(session)
    success = AuditRecord(
        action="login", target_type="user", target_id="u1", outcome="success", correlation_id="c1"
    )
    failure = AuditRecord(
        action="login", target_type="user", target_id="u1", outcome="failure", correlation_id="c2"
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
        action="login",
        target_type="user",
        target_id="u-role-check",
        outcome="success",
        correlation_id="c-role-check",
    )
    await repo.record(entry)  # must not raise — INSERT is granted

    # Read back via the unrestricted `session`, not `audit_writer_session`:
    # the role is deliberately INSERT-only, so it cannot SELECT its own
    # rows back either — verifying via that same restricted connection
    # would conflate "can insert" with "can insert and read", which is
    # not the guarantee being tested here.
    result = await session.execute(
        select(AuditLogModel).where(AuditLogModel.target_id == "u-role-check")
    )
    assert result.scalar_one().outcome == "success"


async def test_audit_repository__connection_actually_restricted_to_audit_writer_role__update_is_denied(
    audit_writer_session, session
):
    # Seed a row via the unrestricted session (repository under test is
    # never used to write here — this is only proving the *connection*
    # AUDIT_WRITER_ROLE resolves to cannot UPDATE, independent of the
    # repository's own code path).
    repo = PostgresAuditRepository(session)
    entry = AuditRecord(
        action="login",
        target_type="user",
        target_id="u-update-check",
        outcome="failure",
        correlation_id="c-update-check",
    )
    await repo.record(entry)

    with pytest.raises(DBAPIError, match="permission denied"):
        await audit_writer_session.execute(
            text("UPDATE audit_log SET outcome = 'success' WHERE target_id = 'u-update-check'")
        )
