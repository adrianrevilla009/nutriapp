"""Guards infrastructure/http/error_mapping.py's exception -> HTTP status
table. Found live (2026-09-14): a Stripe checkout-session creation
failure (PaymentProviderUnavailableError, e.g. an invalid/placeholder API
key rejected with a 401) was falling through to the generic, unmapped-
exception 500 path instead of a real "service temporarily unavailable"
signal -- CLAUDE.md section 2.6 requires an explicit, documented fallback
for every external-API failure, not a bare 500."""

from __future__ import annotations

import json

from domain.ports.payment_provider_port import PaymentProviderUnavailableError
from infrastructure.http.error_mapping import map_exception


def test_payment_provider_unavailable_maps_to_503_not_a_bare_500():
    response = map_exception(PaymentProviderUnavailableError("Stripe rejected the request (401)."))

    assert response.status_code == 503
    body = json.loads(response.body)
    assert body["code"] == "PAYMENT_PROVIDER_UNAVAILABLE"
    assert "Stripe rejected the request (401)." in body["error"]


def test_unrecognized_exception_still_falls_back_to_generic_500():
    response = map_exception(RuntimeError("something genuinely unexpected"))

    assert response.status_code == 500
    body = json.loads(response.body)
    assert body["code"] == "INTERNAL_ERROR"
