import uuid
from datetime import datetime, timedelta, timezone

import pytest

from application.commands.reveal_token_secret import (
    RevealTokenSecretCommand,
    RevealTokenSecretHandler,
)
from application.errors import InvalidCallerCredentialError, InvalidTokenError
from domain.entities.token import SecretReferenceToken, SecretTokenKind
from tests.fixtures.fakes import FakeAuditRepository, FakeTokenRepository

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
CREDENTIAL = "internal-shared-secret"


def setup(expired=False):
    tokens = FakeTokenRepository()
    audit = FakeAuditRepository()
    token = SecretReferenceToken(
        reference_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        kind=SecretTokenKind.EMAIL_VERIFICATION,
        secret_hash="hash",
        created_at=NOW,
        expires_at=NOW - timedelta(seconds=1) if expired else NOW + timedelta(hours=24),
        raw_secret="the-raw-secret",
    )
    tokens.secret_tokens[token.reference_id] = token
    handler = RevealTokenSecretHandler(tokens, audit, CREDENTIAL, now_fn=lambda: NOW)
    return handler, tokens, audit, token


async def test_reveal__valid_not_yet_revealed__returns_raw_secret_once_and_marks_revealed():
    handler, tokens, audit, token = setup()

    result = await handler.handle(
        RevealTokenSecretCommand(
            reference_id=str(token.reference_id),
            caller_service_credential=CREDENTIAL,
            correlation_id="c1",
        )
    )

    assert result.secret == "the-raw-secret"
    assert tokens.secret_tokens[token.reference_id].revealed_at == NOW
    assert audit.records[-1].outcome == "success"


async def test_reveal__second_attempt_on_same_reference_id__rejected_replay_defense():
    handler, tokens, audit, token = setup()
    await handler.handle(
        RevealTokenSecretCommand(
            reference_id=str(token.reference_id),
            caller_service_credential=CREDENTIAL,
            correlation_id="c1",
        )
    )

    replay_command = RevealTokenSecretCommand(
        reference_id=str(token.reference_id),
        caller_service_credential=CREDENTIAL,
        correlation_id="c2",
    )
    with pytest.raises(InvalidTokenError):
        await handler.handle(replay_command)
    assert audit.records[-1].outcome == "failure"


async def test_reveal__expired_reference_id__rejected():
    handler, tokens, audit, token = setup(expired=True)

    command = RevealTokenSecretCommand(
        reference_id=str(token.reference_id),
        caller_service_credential=CREDENTIAL,
        correlation_id="c1",
    )
    with pytest.raises(InvalidTokenError):
        await handler.handle(command)


async def test_reveal__caller_without_valid_credentials__rejected_and_audited():
    handler, tokens, audit, token = setup()

    command = RevealTokenSecretCommand(
        reference_id=str(token.reference_id),
        caller_service_credential="wrong-credential",
        correlation_id="c1",
    )
    with pytest.raises(InvalidCallerCredentialError):
        await handler.handle(command)
    assert audit.records[-1].outcome == "failure"
    assert audit.records[-1].metadata["reason"] == "invalid_caller_credential"


async def test_reveal__every_attempt_success_or_not__writes_an_audit_record():
    handler, tokens, audit, token = setup()
    assert len(audit.records) == 0

    await handler.handle(
        RevealTokenSecretCommand(
            reference_id=str(token.reference_id),
            caller_service_credential=CREDENTIAL,
            correlation_id="c1",
        )
    )
    assert len(audit.records) == 1

    second_command = RevealTokenSecretCommand(
        reference_id=str(token.reference_id),
        caller_service_credential=CREDENTIAL,
        correlation_id="c2",
    )
    with pytest.raises(InvalidTokenError):
        await handler.handle(second_command)
    assert len(audit.records) == 2
