"""Integration tests: PostgresExportAuditRepository against real
(testcontainers) Postgres, including proof that the append-only DB role
(AUDIT_WRITER_ROLE, "analytics_service_audit_writer") is genuinely
enforced at the connection level, not just documented -- the exact gap a
security review flagged in the pre-fix `export_audit_log` table
(identity-service's/profile-service's `test_postgres_audit_repository.py`
precedent, mirrored here)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from domain.value_objects.export_outcome import ExportOutcome
from infrastructure.composition_root import AUDIT_WRITER_ROLE
from infrastructure.persistence.models import ExportAuditLogModel
from infrastructure.persistence.postgres_export_audit_repository import (
    PostgresExportAuditRepository,
)

START = date(2026, 6, 1)
END = date(2026, 6, 8)
REQUESTED_AT = datetime(2026, 6, 8, tzinfo=timezone.utc)


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
        await conn.execute(text(f'GRANT USAGE ON SCHEMA analytics_audit TO "{AUDIT_WRITER_ROLE}"'))
        await conn.execute(
            text(
                f'GRANT SELECT, INSERT ON analytics_audit.export_audit_log TO "{AUDIT_WRITER_ROLE}"'
            )
        )
        await conn.execute(
            text(
                f"REVOKE UPDATE, DELETE ON analytics_audit.export_audit_log "
                f'FROM "{AUDIT_WRITER_ROLE}"'
            )
        )
        await conn.execute(text(f'GRANT "{AUDIT_WRITER_ROLE}" TO "{current_user}"'))

    restricted_engine = create_async_engine(
        postgres_async_url,
        connect_args={"server_settings": {"role": AUDIT_WRITER_ROLE}},
    )
    async with AsyncSession(restricted_engine, expire_on_commit=False) as s:
        yield s
    await restricted_engine.dispose()


def _record_kwargs(**overrides):
    user_id = overrides.pop("user_id", uuid.uuid4())
    base = dict(
        user_id=user_id,
        report_type="full",
        requested_at=REQUESTED_AT,
        export_format="csv",
        start_date=START,
        end_date=END,
        row_count=3,
        outcome=ExportOutcome.SUCCESS,
        actor_id=user_id,
        action="export_report",
        target_type="full",
        target_id=f"{START.isoformat()}..{END.isoformat()}",
        correlation_id="corr-1",
    )
    base.update(overrides)
    return base


async def test_export_audit_repository__record__is_persisted_and_readable(session):
    repo = PostgresExportAuditRepository(session)
    kwargs = _record_kwargs()

    await repo.record(**kwargs)

    result = await session.execute(
        select(ExportAuditLogModel).where(
            ExportAuditLogModel.correlation_id == kwargs["correlation_id"]
        )
    )
    row = result.scalar_one()
    assert row.outcome == "success"
    assert row.actor_id == kwargs["actor_id"]
    assert row.action == "export_report"
    assert row.target_type == "full"
    assert row.target_id == kwargs["target_id"]
    assert row.correlation_id == "corr-1"
    assert row.row_count == 3


async def test_export_audit_repository__round_trips_rejected_outcome_and_metadata(session):
    repo = PostgresExportAuditRepository(session)
    kwargs = _record_kwargs(
        outcome=ExportOutcome.REJECTED,
        row_count=0,
        correlation_id="corr-rejected",
        rejection_reason="not_entitled",
    )

    await repo.record(**kwargs)

    result = await session.execute(
        select(ExportAuditLogModel).where(ExportAuditLogModel.correlation_id == "corr-rejected")
    )
    row = result.scalar_one()
    assert row.outcome == "rejected"
    assert row.audit_metadata == {"rejection_reason": "not_entitled"}


async def test_export_audit_repository__every_call_produces_its_own_record(session):
    """Not deduplicated like event-consumption idempotency -- every export
    request (success or rejection) is its own audit fact."""
    repo = PostgresExportAuditRepository(session)
    user_id = uuid.uuid4()

    await repo.record(**_record_kwargs(user_id=user_id, correlation_id="dup-1"))
    await repo.record(**_record_kwargs(user_id=user_id, correlation_id="dup-1"))

    result = await session.execute(
        select(ExportAuditLogModel).where(ExportAuditLogModel.correlation_id == "dup-1")
    )
    rows = result.scalars().all()
    assert len(rows) == 2


async def test_export_audit_repository__connection_actually_restricted_to_audit_writer_role__insert_succeeds(
    audit_writer_session, session
):
    repo = PostgresExportAuditRepository(audit_writer_session)
    kwargs = _record_kwargs(correlation_id="corr-role-check")

    await repo.record(**kwargs)  # must not raise -- INSERT is granted

    # Read back via the unrestricted `session`, not `audit_writer_session`:
    # the role is deliberately INSERT/SELECT-only on the table it owns no
    # special rights to beyond that, matching identity-service's precedent
    # of reading back through the unrestricted connection.
    result = await session.execute(
        select(ExportAuditLogModel).where(ExportAuditLogModel.correlation_id == "corr-role-check")
    )
    assert result.scalar_one().outcome == "success"


async def test_export_audit_repository__connection_actually_restricted_to_audit_writer_role__update_is_denied(
    audit_writer_session, session
):
    repo = PostgresExportAuditRepository(session)
    kwargs = _record_kwargs(correlation_id="corr-update-check")
    await repo.record(**kwargs)

    stmt = text(
        "UPDATE analytics_audit.export_audit_log SET outcome = 'success' "
        "WHERE correlation_id = 'corr-update-check'"
    )
    with pytest.raises(DBAPIError, match="permission denied"):
        await audit_writer_session.execute(stmt)


async def test_export_audit_repository__connection_actually_restricted_to_audit_writer_role__delete_is_denied(
    audit_writer_session, session
):
    repo = PostgresExportAuditRepository(session)
    kwargs = _record_kwargs(correlation_id="corr-delete-check")
    await repo.record(**kwargs)

    stmt = text(
        "DELETE FROM analytics_audit.export_audit_log WHERE correlation_id = 'corr-delete-check'"
    )
    with pytest.raises(DBAPIError, match="permission denied"):
        await audit_writer_session.execute(stmt)
