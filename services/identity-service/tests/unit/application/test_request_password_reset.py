import pytest

from application.commands.request_password_reset import (
    RequestPasswordResetCommand,
    RequestPasswordResetHandler,
    RequestPasswordResetResult,
)
from application.errors import RateLimitedError
from domain.entities.user import User
from domain.value_objects.email import Email
from tests.fixtures.fakes import (
    FakeOutboxRepository,
    FakeRateLimiter,
    FakeTokenRepository,
    FakeUserRepository,
)


def make_handler():
    users = FakeUserRepository()
    tokens = FakeTokenRepository()
    outbox = FakeOutboxRepository()
    rate_limiter = FakeRateLimiter()
    handler = RequestPasswordResetHandler(users, tokens, outbox, rate_limiter)
    return handler, users, tokens, outbox, rate_limiter


async def test_request_password_reset__existing_user__generates_token_and_publishes_event():
    handler, users, tokens, outbox, rl = make_handler()
    user = User.register(Email("user@example.com"), "hashed")
    user.verify_email()
    await users.save(user)

    result1 = await handler.handle(
        RequestPasswordResetCommand(
            email="user@example.com", correlation_id="c1", client_ip="1.2.3.4"
        )
    )

    assert len(tokens.secret_tokens) == 1
    assert len(outbox.enqueued) == 1
    assert outbox.enqueued[0].event_type == "PasswordResetRequested"
    assert "reset_token_reference_id" in outbox.enqueued[0].payload
    assert isinstance(result1, RequestPasswordResetResult)


async def test_request_password_reset__unknown_email__identical_response_no_side_effects():
    handler, users, tokens, outbox, rl = make_handler()

    result = await handler.handle(
        RequestPasswordResetCommand(
            email="nobody@example.com", correlation_id="c1", client_ip="1.2.3.4"
        )
    )

    assert len(tokens.secret_tokens) == 0
    assert len(outbox.enqueued) == 0
    assert isinstance(result, RequestPasswordResetResult)


async def test_request_password_reset__rate_limit_exceeded__rejected_before_token_generation():
    handler, users, tokens, outbox, rl = make_handler()
    rl.should_exceed = True

    with pytest.raises(RateLimitedError):
        await handler.handle(
            RequestPasswordResetCommand(
                email="user@example.com", correlation_id="c1", client_ip="1.2.3.4"
            )
        )

    assert len(tokens.secret_tokens) == 0
