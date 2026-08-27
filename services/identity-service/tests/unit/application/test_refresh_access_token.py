import uuid
from datetime import datetime, timedelta, timezone

import pytest

from application.commands.refresh_access_token import (
    RefreshAccessTokenCommand,
    RefreshAccessTokenHandler,
)
from application.security.token_generation import hash_secret
from domain.entities.token import RefreshToken, TokenExpiredError, TokenRevokedError
from domain.entities.user import User
from domain.value_objects.email import Email
from tests.fixtures.fakes import FakeTokenIssuer, FakeTokenRepository, FakeUserRepository

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


async def setup(expired=False, revoked=False):
    users = FakeUserRepository()
    tokens = FakeTokenRepository()
    issuer = FakeTokenIssuer()
    user = User.register(Email("user@example.com"), "hashed")
    await users.save(user)
    secret = "raw-refresh-secret"
    token = RefreshToken(
        token_id=uuid.uuid4(),
        user_id=user.user_id,
        token_hash=hash_secret(secret),
        created_at=NOW,
        expires_at=NOW - timedelta(seconds=1) if expired else NOW + timedelta(days=30),
    )
    if revoked:
        token.revoke(NOW)
    tokens.refresh_tokens[token.token_id] = token
    handler = RefreshAccessTokenHandler(tokens, users, issuer, now_fn=lambda: NOW)
    return handler, secret


async def test_refresh__valid_token__issues_new_access_token_without_rotating_refresh():
    handler, secret = await setup()
    result = await handler.handle(
        RefreshAccessTokenCommand(refresh_token=secret, correlation_id="c1")
    )
    assert result.access_token


async def test_refresh__revoked_token__raises_token_revoked_error():
    handler, secret = await setup(revoked=True)
    command = RefreshAccessTokenCommand(refresh_token=secret, correlation_id="c1")
    with pytest.raises(TokenRevokedError):
        await handler.handle(command)


async def test_refresh__expired_token__raises_token_expired_error():
    handler, secret = await setup(expired=True)
    command = RefreshAccessTokenCommand(refresh_token=secret, correlation_id="c1")
    with pytest.raises(TokenExpiredError):
        await handler.handle(command)
