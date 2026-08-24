import uuid
from datetime import datetime, timedelta, timezone

import pytest

from application.commands.verify_email import VerifyEmailCommand, VerifyEmailHandler
from application.errors import InvalidTokenError
from application.security.token_generation import hash_secret
from domain.entities.token import SecretReferenceToken, SecretTokenKind
from domain.entities.user import User, UserStatus
from domain.value_objects.email import Email
from tests.fixtures.fakes import FakeAuditRepository, FakeTokenRepository, FakeUserRepository

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def setup(now=NOW, expired=False):
    users = FakeUserRepository()
    tokens = FakeTokenRepository()
    audit = FakeAuditRepository()
    user = User.register(Email("verify@example.com"), "hashed")
    users._by_id[user.user_id] = user
    secret = "raw-secret"
    token = SecretReferenceToken(
        reference_id=uuid.uuid4(),
        user_id=user.user_id,
        kind=SecretTokenKind.EMAIL_VERIFICATION,
        secret_hash=hash_secret(secret),
        created_at=now - timedelta(hours=1),
        expires_at=now - timedelta(seconds=1) if expired else now + timedelta(hours=23),
        raw_secret=secret,
    )
    tokens.secret_tokens[token.reference_id] = token
    handler = VerifyEmailHandler(users, tokens, audit, now_fn=lambda: now)
    return handler, users, tokens, audit, user, token, secret


async def test_verify_email__valid_token__activates_user_and_audits_success():
    handler, users, tokens, audit, user, token, secret = setup()
    result = await handler.handle(
        VerifyEmailCommand(
            reference_id=str(token.reference_id), secret=secret, correlation_id="c1"
        )
    )
    saved = await users.get_by_id(result.user_id)
    assert saved.status == UserStatus.ACTIVE
    assert audit.records[-1].action == "email_verified"
    assert audit.records[-1].outcome == "success"


async def test_verify_email__unknown_token__rejected_generic_error_and_audits_failure():
    handler, users, tokens, audit, user, token, secret = setup()
    with pytest.raises(InvalidTokenError):
        await handler.handle(
            VerifyEmailCommand(
                reference_id=str(uuid.uuid4()), secret=secret, correlation_id="c1"
            )
        )
    assert audit.records[-1].outcome == "failure"


async def test_verify_email__expired_token__rejected_generic_error_and_audits_failure():
    handler, users, tokens, audit, user, token, secret = setup(expired=True)
    with pytest.raises(InvalidTokenError):
        await handler.handle(
            VerifyEmailCommand(
                reference_id=str(token.reference_id), secret=secret, correlation_id="c1"
            )
        )
    assert audit.records[-1].outcome == "failure"


async def test_verify_email__already_used_token__rejected_generic_error():
    handler, users, tokens, audit, user, token, secret = setup()
    await handler.handle(
        VerifyEmailCommand(
            reference_id=str(token.reference_id), secret=secret, correlation_id="c1"
        )
    )
    # Second handler instance operating on a freshly-PENDING user simulates
    # a second redemption attempt of the same already-used token.
    with pytest.raises(InvalidTokenError):
        await handler.handle(
            VerifyEmailCommand(
                reference_id=str(token.reference_id), secret=secret, correlation_id="c2"
            )
        )
    assert audit.records[-1].outcome == "failure"
