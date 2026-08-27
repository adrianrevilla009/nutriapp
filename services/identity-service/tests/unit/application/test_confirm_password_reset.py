import uuid
from datetime import datetime, timedelta, timezone

import pytest

from application.commands.confirm_password_reset import (
    ConfirmPasswordResetCommand,
    ConfirmPasswordResetHandler,
)
from application.errors import InvalidTokenError
from application.security.token_generation import hash_secret
from domain.entities.token import RefreshToken, SecretReferenceToken, SecretTokenKind
from domain.entities.user import User
from domain.value_objects.email import Email
from domain.value_objects.password import WeakPasswordError
from tests.fixtures.fakes import (
    FakeAuditRepository,
    FakePasswordHasher,
    FakeTokenRepository,
    FakeUserRepository,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


async def setup(expired=False):
    users = FakeUserRepository()
    tokens = FakeTokenRepository()
    hasher = FakePasswordHasher()
    audit = FakeAuditRepository()
    user = User.register(Email("user@example.com"), "hashed:OldPassw0rd!")
    user.verify_email()
    await users.save(user)

    existing_refresh = RefreshToken(
        token_id=uuid.uuid4(),
        user_id=user.user_id,
        token_hash="some-hash",
        created_at=NOW,
        expires_at=NOW + timedelta(days=30),
    )
    tokens.refresh_tokens[existing_refresh.token_id] = existing_refresh

    secret = "raw-reset-secret"
    token = SecretReferenceToken(
        reference_id=uuid.uuid4(),
        user_id=user.user_id,
        kind=SecretTokenKind.PASSWORD_RESET,
        secret_hash=hash_secret(secret),
        created_at=NOW,
        expires_at=NOW - timedelta(seconds=1) if expired else NOW + timedelta(hours=1),
        raw_secret=secret,
    )
    tokens.secret_tokens[token.reference_id] = token

    handler = ConfirmPasswordResetHandler(users, tokens, hasher, audit, now_fn=lambda: NOW)
    return handler, users, tokens, audit, user, token, secret, existing_refresh


async def test_confirm_password_reset__valid_token_and_strong_password__updates_and_revokes_refresh_tokens():
    handler, users, tokens, audit, user, token, secret, refresh = await setup()

    result = await handler.handle(
        ConfirmPasswordResetCommand(
            reference_id=str(token.reference_id),
            secret=secret,
            new_password="Str0ng!NewPassw0rd",
            correlation_id="c1",
        )
    )

    saved_user = await users.get_by_id(result.user_id)
    assert saved_user.password_hash == "hashed:Str0ng!NewPassw0rd"
    assert tokens.refresh_tokens[refresh.token_id].is_revoked()
    assert audit.records[-1].action == "password_change"
    assert audit.records[-1].outcome == "success"


async def test_confirm_password_reset__expired_token__rejected_and_audits_failure():
    handler, users, tokens, audit, user, token, secret, refresh = await setup(expired=True)

    command = ConfirmPasswordResetCommand(
        reference_id=str(token.reference_id),
        secret=secret,
        new_password="Str0ng!NewPassw0rd",
        correlation_id="c1",
    )
    with pytest.raises(InvalidTokenError):
        await handler.handle(command)
    assert audit.records[-1].outcome == "failure"


async def test_confirm_password_reset__unknown_token__rejected():
    handler, users, tokens, audit, user, token, secret, refresh = await setup()

    command = ConfirmPasswordResetCommand(
        reference_id=str(uuid.uuid4()),
        secret=secret,
        new_password="Str0ng!NewPassw0rd",
        correlation_id="c1",
    )
    with pytest.raises(InvalidTokenError):
        await handler.handle(command)


async def test_confirm_password_reset__weak_password__rejected_before_touching_repository():
    handler, users, tokens, audit, user, token, secret, refresh = await setup()

    command = ConfirmPasswordResetCommand(
        reference_id=str(token.reference_id),
        secret=secret,
        new_password="weak",
        correlation_id="c1",
    )
    with pytest.raises(WeakPasswordError):
        await handler.handle(command)
    assert tokens.secret_tokens[token.reference_id].used_at is None
