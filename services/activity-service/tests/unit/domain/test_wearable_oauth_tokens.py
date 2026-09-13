"""WearableOAuthTokens -- test-plan addendum (2026-09-11) section 1."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from domain.value_objects.wearable_oauth_tokens import (
    InvalidWearableTokensError,
    WearableOAuthTokens,
)


def _tokens(**overrides: object) -> WearableOAuthTokens:
    defaults: dict[str, object] = dict(
        access_token="access-secret-value",
        refresh_token="refresh-secret-value",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    defaults.update(overrides)
    return WearableOAuthTokens(**defaults)  # type: ignore[arg-type]


def test_valid_tokens_constructed():
    tokens = _tokens()
    assert tokens.access_token == "access-secret-value"
    assert tokens.refresh_token == "refresh-secret-value"


def test_empty_access_token_raises():
    with pytest.raises(InvalidWearableTokensError):
        _tokens(access_token="")


def test_empty_refresh_token_raises():
    with pytest.raises(InvalidWearableTokensError):
        _tokens(refresh_token="")


def test_repr_and_str_never_leak_raw_token_values():
    tokens = _tokens(access_token="super-secret-access", refresh_token="super-secret-refresh")
    assert "super-secret-access" not in repr(tokens)
    assert "super-secret-access" not in str(tokens)
    assert "super-secret-refresh" not in repr(tokens)
    assert "super-secret-refresh" not in str(tokens)


def test_is_expired_true_once_now_reaches_expiry():
    expiry = datetime(2026, 1, 1, tzinfo=timezone.utc)
    tokens = _tokens(expires_at=expiry)
    assert tokens.is_expired(now=expiry) is True
    assert tokens.is_expired(now=expiry + timedelta(seconds=1)) is True


def test_is_expired_false_before_expiry():
    expiry = datetime(2026, 1, 1, tzinfo=timezone.utc)
    tokens = _tokens(expires_at=expiry)
    assert tokens.is_expired(now=expiry - timedelta(seconds=1)) is False
