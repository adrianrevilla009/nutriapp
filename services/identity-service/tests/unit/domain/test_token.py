import uuid
from datetime import datetime, timedelta, timezone

import pytest

from domain.entities.token import (
    RefreshToken,
    SecretReferenceToken,
    SecretTokenKind,
    TokenAlreadyRevealedError,
    TokenAlreadyUsedError,
    TokenExpiredError,
    TokenRevokedError,
    TokenSecretMismatchError,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_refresh_token(**overrides) -> RefreshToken:
    defaults = dict(
        token_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        token_hash="hash",
        created_at=NOW,
        expires_at=NOW + timedelta(days=30),
    )
    defaults.update(overrides)
    return RefreshToken(**defaults)


def make_secret_token(**overrides) -> SecretReferenceToken:
    defaults = dict(
        reference_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        kind=SecretTokenKind.EMAIL_VERIFICATION,
        secret_hash="secret-hash",
        created_at=NOW,
        expires_at=NOW + timedelta(hours=24),
        raw_secret="raw-secret",
    )
    defaults.update(overrides)
    return SecretReferenceToken(**defaults)


def test_refresh_token__is_expired__false_before_ttl():
    token = make_refresh_token()
    assert token.is_expired(NOW + timedelta(days=1)) is False


def test_refresh_token__is_expired__true_after_ttl():
    token = make_refresh_token()
    assert token.is_expired(NOW + timedelta(days=31)) is True


def test_refresh_token__ensure_usable_when_expired__raises_token_expired_error():
    token = make_refresh_token()
    with pytest.raises(TokenExpiredError):
        token.ensure_usable(NOW + timedelta(days=31))


def test_refresh_token__ensure_usable_when_revoked__raises_token_revoked_error():
    token = make_refresh_token()
    token.revoke(NOW)
    with pytest.raises(TokenRevokedError):
        token.ensure_usable(NOW)


def test_refresh_token__revoke_twice__is_idempotent():
    token = make_refresh_token()
    token.revoke(NOW)
    first_revoked_at = token.revoked_at
    token.revoke(NOW + timedelta(seconds=1))
    assert token.revoked_at == first_revoked_at


def test_secret_token__is_expired__false_before_ttl():
    token = make_secret_token()
    assert token.is_expired(NOW + timedelta(hours=1)) is False


def test_secret_token__is_expired__true_after_ttl():
    token = make_secret_token()
    assert token.is_expired(NOW + timedelta(hours=25)) is True


def test_secret_token__verify_and_mark_used_then_reused__raises_token_already_used_error():
    token = make_secret_token()
    token.verify_and_mark_used("secret-hash", NOW)
    with pytest.raises(TokenAlreadyUsedError):
        token.verify_and_mark_used("secret-hash", NOW)


def test_secret_token__verify_expired_token__raises_token_expired_error():
    token = make_secret_token()
    with pytest.raises(TokenExpiredError):
        token.verify_and_mark_used("secret-hash", NOW + timedelta(hours=25))


def test_secret_token__verify_with_wrong_secret_hash__raises_token_secret_mismatch_error():
    token = make_secret_token()
    with pytest.raises(TokenSecretMismatchError):
        token.verify_and_mark_used("wrong-hash", NOW)


def test_secret_token__reveal__returns_secret_once_and_clears_it():
    token = make_secret_token()
    secret = token.reveal(NOW)
    assert secret == "raw-secret"
    assert token.raw_secret is None
    assert token.revealed_at == NOW


def test_secret_token__reveal_twice__raises_token_already_revealed_error():
    token = make_secret_token()
    token.reveal(NOW)
    with pytest.raises(TokenAlreadyRevealedError):
        token.reveal(NOW)


def test_secret_token__reveal_expired_token__raises_token_expired_error():
    token = make_secret_token()
    with pytest.raises(TokenExpiredError):
        token.reveal(NOW + timedelta(hours=25))
