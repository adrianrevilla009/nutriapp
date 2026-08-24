import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.token import RefreshToken, SecretReferenceToken, SecretTokenKind
from domain.entities.user import User
from domain.value_objects.email import Email
from infrastructure.persistence.postgres_token_repository import PostgresTokenRepository
from infrastructure.persistence.postgres_user_repository import PostgresUserRepository

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
async def session(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as s:
        yield s


@pytest.fixture()
async def existing_user(session):
    users = PostgresUserRepository(session)
    user = User.register(Email("tokenowner@example.com"), "hashed")
    await users.save(user)
    await session.commit()
    return user


async def test_refresh_token__save_then_get_by_hash__round_trips(session, existing_user):
    repo = PostgresTokenRepository(session)
    token = RefreshToken(
        token_id=uuid.uuid4(),
        user_id=existing_user.user_id,
        token_hash="hash-abc",
        created_at=NOW,
        expires_at=NOW + timedelta(days=30),
    )
    await repo.save_refresh_token(token)
    await session.commit()

    fetched = await repo.get_refresh_token_by_hash("hash-abc")
    assert fetched is not None
    assert fetched.token_id == token.token_id


async def test_refresh_token__revoke_persists_and_is_immediately_reflected(session, existing_user):
    repo = PostgresTokenRepository(session)
    token = RefreshToken(
        token_id=uuid.uuid4(),
        user_id=existing_user.user_id,
        token_hash="hash-def",
        created_at=NOW,
        expires_at=NOW + timedelta(days=30),
    )
    await repo.save_refresh_token(token)
    token.revoke(NOW)
    await repo.save_refresh_token(token)
    await session.commit()

    fetched = await repo.get_refresh_token(token.token_id)
    assert fetched.is_revoked()


async def test_secret_token__save_then_get__round_trips_for_email_verification_and_password_reset(
    session, existing_user
):
    repo = PostgresTokenRepository(session)
    for kind in (SecretTokenKind.EMAIL_VERIFICATION, SecretTokenKind.PASSWORD_RESET):
        token = SecretReferenceToken(
            reference_id=uuid.uuid4(),
            user_id=existing_user.user_id,
            kind=kind,
            secret_hash="hash",
            created_at=NOW,
            expires_at=NOW + timedelta(hours=1),
            raw_secret="raw",
        )
        await repo.save_secret_token(token)
        await session.commit()

        fetched = await repo.get_secret_token(token.reference_id)
        assert fetched is not None
        assert fetched.kind == kind


async def test_secret_token__expired_token_remains_readable_not_silently_deleted(
    session, existing_user
):
    repo = PostgresTokenRepository(session)
    token = SecretReferenceToken(
        reference_id=uuid.uuid4(),
        user_id=existing_user.user_id,
        kind=SecretTokenKind.EMAIL_VERIFICATION,
        secret_hash="hash",
        created_at=NOW,
        expires_at=NOW - timedelta(hours=1),
        raw_secret="raw",
    )
    await repo.save_secret_token(token)
    await session.commit()

    fetched = await repo.get_secret_token(token.reference_id)
    assert fetched is not None
    assert fetched.is_expired(NOW) is True
