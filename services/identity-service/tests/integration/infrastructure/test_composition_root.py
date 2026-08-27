"""Proves Container.audit_engine's privilege restriction end-to-end, by
constructing the *real* Container class (not a reimplementation of its
`connect_args`/SET ROLE mechanism) against a live Postgres — a gap flagged
in `/test-review`: the existing tests in test_postgres_audit_repository.py
independently re-create the same connect_args pattern rather than
exercising Container.__init__ itself, so a future typo/removal there
would go undetected by every other test.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from domain.entities.audit_record import AuditRecord
from infrastructure.composition_root import AUDIT_WRITER_ROLE, Container, Settings
from infrastructure.persistence.postgres_audit_repository import PostgresAuditRepository
from infrastructure.security.jwt_token_issuer import generate_rsa_key_pair


@pytest.fixture
async def real_container(db_engine, postgres_async_url):
    # Simulates infra/k8s/charts/_lib/templates/_db-provision-job.tpl's
    # audit-writer role creation (idempotent — the underlying container
    # is session-scoped, this fixture may run more than once against it).
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
        await conn.execute(text(f"GRANT INSERT ON audit_log TO {AUDIT_WRITER_ROLE}"))
        await conn.execute(text(f"REVOKE UPDATE, DELETE ON audit_log FROM {AUDIT_WRITER_ROLE}"))
        await conn.execute(text(f'GRANT "{AUDIT_WRITER_ROLE}" TO "{current_user}"'))

    private_pem, public_pem = generate_rsa_key_pair()
    settings = Settings(
        database_url=postgres_async_url,
        redis_url="redis://localhost:6379/0",  # never connected to in this test
        rabbitmq_url="amqp://guest:guest@localhost/",  # never connected to in this test
        jwt_private_key_pem=private_pem,
        jwt_public_key_pem=public_pem,
        jwt_key_id="test-key-1",
        internal_reveal_credential="test-internal-credential",
        access_token_ttl=timedelta(minutes=15),
    )
    container = Container(settings)
    yield container
    await container.engine.dispose()
    await container.audit_engine.dispose()
    await container.redis.aclose()


async def test_container__new_audit_session__insert_succeeds(real_container):
    async with real_container.new_audit_session() as audit_session:
        repo = PostgresAuditRepository(audit_session)
        entry = AuditRecord(
            action="login",
            target_type="user",
            target_id="u-container-check",
            outcome="success",
            correlation_id="c-container-check",
        )
        await repo.record(entry)  # must not raise — proves the real Container wiring works


async def test_container__new_audit_session__update_is_denied_by_postgres(real_container):
    async with real_container.new_audit_session() as audit_session:
        with pytest.raises(DBAPIError, match="permission denied"):
            await audit_session.execute(
                text(
                    "UPDATE audit_log SET outcome = 'tampered' "
                    "WHERE target_id = 'u-container-check'"
                )
            )
