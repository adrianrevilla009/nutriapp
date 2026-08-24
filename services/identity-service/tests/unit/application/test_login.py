import pytest

from application.commands.login import LoginCommand, LoginHandler
from application.errors import InvalidCredentialsError, RateLimitedError
from domain.entities.user import User
from domain.value_objects.email import Email
from tests.fixtures.fakes import (
    FakeAuditRepository,
    FakeOutboxRepository,
    FakePasswordHasher,
    FakeRateLimiter,
    FakeTokenIssuer,
    FakeTokenRepository,
    FakeUserRepository,
)


def make_handler():
    users = FakeUserRepository()
    tokens = FakeTokenRepository()
    outbox = FakeOutboxRepository()
    hasher = FakePasswordHasher()
    issuer = FakeTokenIssuer()
    rate_limiter = FakeRateLimiter()
    audit = FakeAuditRepository()
    handler = LoginHandler(users, tokens, outbox, hasher, issuer, rate_limiter, audit)
    return handler, users, tokens, outbox, rate_limiter, audit


async def make_verified_user(users, email="user@example.com", password="Str0ng!Passw0rd"):
    user = User.register(Email(email), f"hashed:{password}")
    user.verify_email()
    await users.save(user)
    return user


def command(email="user@example.com", password="Str0ng!Passw0rd", ip="1.2.3.4", ua="UA-1"):
    return LoginCommand(
        email=email, password=password, correlation_id="c1", client_ip=ip, user_agent=ua
    )


async def test_login__correct_credentials_verified_unlocked__issues_tokens_and_audits_success():
    handler, users, tokens, outbox, rl, audit = make_handler()
    await make_verified_user(users)

    result = await handler.handle(command())

    assert result.access_token
    assert result.refresh_token
    assert audit.records[-1].action == "login"
    assert audit.records[-1].outcome == "success"


async def test_login__wrong_password_and_unknown_email__produce_identical_error_shape():
    handler, users, tokens, outbox, rl, audit = make_handler()
    await make_verified_user(users)

    with pytest.raises(InvalidCredentialsError) as wrong_password_exc:
        await handler.handle(command(password="WrongPassword!1"))

    with pytest.raises(InvalidCredentialsError) as unknown_email_exc:
        await handler.handle(command(email="nobody@example.com"))

    assert str(wrong_password_exc.value) == str(unknown_email_exc.value)


async def test_login__unverified_account__rejected_generic_error_audit_has_specific_reason():
    handler, users, tokens, outbox, rl, audit = make_handler()
    user = User.register(Email("pending@example.com"), "hashed:Str0ng!Passw0rd")
    await users.save(user)

    with pytest.raises(InvalidCredentialsError):
        await handler.handle(command(email="pending@example.com"))

    assert audit.records[-1].metadata["reason"] == "email_not_verified"


async def test_login__locked_account__rejected_generic_error_audit_has_specific_reason():
    handler, users, tokens, outbox, rl, audit = make_handler()
    user = await make_verified_user(users, email="locked@example.com")
    for _ in range(5):
        user.record_login_failure()
    await users.save(user)

    with pytest.raises(InvalidCredentialsError):
        await handler.handle(command(email="locked@example.com"))

    assert audit.records[-1].metadata["reason"] == "account_locked"


async def test_login__rate_limit_exceeded__rejected_before_touching_repository():
    handler, users, tokens, outbox, rl, audit = make_handler()
    rl.should_exceed = True

    with pytest.raises(RateLimitedError):
        await handler.handle(command())

    assert audit.records[-1].metadata["reason"] == "rate_limited"


async def test_login__unrecognized_device__publishes_new_device_login_detected():
    handler, users, tokens, outbox, rl, audit = make_handler()
    user = await make_verified_user(users)
    user.remember_device("some-other-fingerprint")
    await users.save(user)

    await handler.handle(command(ip="9.9.9.9", ua="UA-new"))

    assert any(e.event_type == "NewDeviceLoginDetected" for e in outbox.enqueued)


async def test_login__known_device__does_not_publish_new_device_login_detected():
    handler, users, tokens, outbox, rl, audit = make_handler()
    await make_verified_user(users)

    # First login from this device establishes it as known but, being the
    # very first login, must not itself be flagged.
    await handler.handle(command(ip="1.2.3.4", ua="UA-1"))
    assert not any(e.event_type == "NewDeviceLoginDetected" for e in outbox.enqueued)

    # Second login from the same device: still not flagged.
    await handler.handle(command(ip="1.2.3.4", ua="UA-1"))
    assert not any(e.event_type == "NewDeviceLoginDetected" for e in outbox.enqueued)
