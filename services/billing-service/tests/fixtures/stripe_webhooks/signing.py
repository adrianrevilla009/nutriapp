"""Offline Stripe-Signature signing helper for fixture webhook payloads --
matches Stripe's documented HMAC scheme exactly
(https://stripe.com/docs/webhooks/signatures#verify-manually). Never a
live call; used only to construct deterministic valid/tampered/wrong-
secret/expired-timestamp test cases."""

from __future__ import annotations

import hashlib
import hmac
import time

TEST_WEBHOOK_SECRET = "whsec_test_fixture_secret"


def sign_payload(
    payload: bytes, secret: str = TEST_WEBHOOK_SECRET, timestamp: int | None = None
) -> str:
    ts = timestamp if timestamp is not None else int(time.time())
    signed_payload = f"{ts}.".encode("ascii") + payload
    signature = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={signature}"
