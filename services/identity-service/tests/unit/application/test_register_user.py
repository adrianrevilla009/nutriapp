import pytest

from application.commands.register_user import RegisterUserCommand, RegisterUserHandler
from domain.services.registration_policy import EmailAlreadyRegisteredError
from domain.value_objects.email import Email
from domain.value_objects.password import WeakPasswordError
from tests.fixtures.fakes import (
    FakeOutboxRepository,
    FakePasswordHasher,
    FakeRateLimiter,
    FakeTokenRepository,
    FakeUserRepository,
)


def make_handler():
    users = FakeUserRepository()
    tokens = FakeTokenRepository()
    outbox = FakeOutboxRepository()
    hasher = FakePasswordHasher()
    rate_limiter = FakeRateLimiter()
    handler = RegisterUserHandler(users, tokens, outbox, hasher, rate_limiter)
    return handler, users, tokens, outbox, rate_limiter


async def test_register_user__valid_input__persists_user_and_enqueues_event():
    handler, users, tokens, outbox, _ = make_handler()
    command = RegisterUserCommand(
        email="new@example.com",
        password="Str0ng!Passw0rd",
        correlation_id="corr-1",
        client_ip="1.2.3.4",
    )

    result = await handler.handle(command)

    saved_user = await users.get_by_id(result.user_id)
    assert saved_user is not None
    assert len(outbox.enqueued) == 1
    assert outbox.enqueued[0].event_type == "UserRegistered"


async def test_register_user__duplicate_email_case_insensitive__raises_and_persists_nothing():
    handler, users, tokens, outbox, _ = make_handler()
    await handler.handle(
        RegisterUserCommand(
            email="dup@example.com",
            password="Str0ng!Passw0rd",
            correlation_id="corr-1",
            client_ip="1.2.3.4",
        )
    )

    with pytest.raises(EmailAlreadyRegisteredError):
        await handler.handle(
            RegisterUserCommand(
                email="DUP@Example.com",
                password="An0ther!Passw0rd",
                correlation_id="corr-2",
                client_ip="1.2.3.4",
            )
        )

    assert len(outbox.enqueued) == 1  # only the first registration


async def test_register_user__weak_password__rejected_before_any_repository_call():
    handler, users, tokens, outbox, _ = make_handler()
    with pytest.raises(WeakPasswordError):
        await handler.handle(
            RegisterUserCommand(
                email="new@example.com",
                password="weak",
                correlation_id="corr-1",
                client_ip="1.2.3.4",
            )
        )
    assert await users.get_by_email(Email("new@example.com")) is None
    assert len(outbox.enqueued) == 0


async def test_register_user__success__event_payload_contains_only_reference_id_not_raw_token():
    handler, users, tokens, outbox, _ = make_handler()
    await handler.handle(
        RegisterUserCommand(
            email="new@example.com",
            password="Str0ng!Passw0rd",
            correlation_id="corr-1",
            client_ip="1.2.3.4",
        )
    )
    event = outbox.enqueued[0]
    payload = event.payload
    assert "email_verification_token_reference_id" in payload
    saved_token = next(iter(tokens.secret_tokens.values()))
    assert payload["email_verification_token_reference_id"] == str(saved_token.reference_id)
    assert saved_token.raw_secret not in str(payload)
