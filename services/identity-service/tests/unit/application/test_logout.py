import uuid
from datetime import datetime, timezone

from application.commands.logout import LogoutCommand, LogoutHandler
from application.security.token_generation import hash_secret
from domain.entities.token import RefreshToken
from tests.fixtures.fakes import FakeAuditRepository, FakeTokenRepository

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_handler():
    tokens = FakeTokenRepository()
    audit = FakeAuditRepository()
    handler = LogoutHandler(tokens, audit, now_fn=lambda: NOW)
    return handler, tokens, audit


async def test_logout__valid_refresh_token__revokes_and_audits_success():
    handler, tokens, audit = make_handler()
    secret = "raw-refresh"
    token = RefreshToken(
        token_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        token_hash=hash_secret(secret),
        created_at=NOW,
        expires_at=NOW,
    )
    tokens.refresh_tokens[token.token_id] = token

    result = await handler.handle(LogoutCommand(refresh_token=secret, correlation_id="c1"))

    assert result.revoked is True
    assert tokens.refresh_tokens[token.token_id].is_revoked()
    assert audit.records[-1].action == "logout"
    assert audit.records[-1].outcome == "success"


async def test_logout__already_revoked_token__idempotent_success_no_error():
    handler, tokens, audit = make_handler()
    secret = "raw-refresh"
    token = RefreshToken(
        token_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        token_hash=hash_secret(secret),
        created_at=NOW,
        expires_at=NOW,
    )
    token.revoke(NOW)
    tokens.refresh_tokens[token.token_id] = token

    result = await handler.handle(LogoutCommand(refresh_token=secret, correlation_id="c1"))
    assert result.revoked is True


async def test_logout__unknown_token__idempotent_success_no_error():
    handler, tokens, audit = make_handler()
    result = await handler.handle(LogoutCommand(refresh_token="never-issued", correlation_id="c1"))
    assert result.revoked is False
