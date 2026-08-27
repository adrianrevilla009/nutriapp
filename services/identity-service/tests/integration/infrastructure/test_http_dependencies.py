"""Pure-logic infra helpers — cheap to test without any real I/O, and
they contain real branching worth covering (X-Forwarded-For parsing,
correlation id passthrough vs. generation)."""

from __future__ import annotations

from starlette.requests import Request

from infrastructure.http.dependencies import get_client_ip, get_correlation_id, get_user_agent


def make_request(headers: dict[str, str], client_host: str | None = "5.6.7.8") -> Request:
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    scope = {
        "type": "http",
        "headers": raw_headers,
        "client": (client_host, 12345) if client_host else None,
    }
    return Request(scope)


def test_get_client_ip__with_x_forwarded_for__uses_first_entry():
    request = make_request({"X-Forwarded-For": "1.2.3.4, 9.9.9.9"})
    assert get_client_ip(request) == "1.2.3.4"


def test_get_client_ip__without_forwarded_header__falls_back_to_client_host():
    request = make_request({})
    assert get_client_ip(request) == "5.6.7.8"


def test_get_client_ip__no_client_at_all__returns_unknown():
    request = make_request({}, client_host=None)
    assert get_client_ip(request) == "unknown"


def test_get_correlation_id__header_present__is_passed_through():
    request = make_request({"X-Correlation-Id": "corr-fixed"})
    assert get_correlation_id(request) == "corr-fixed"


def test_get_correlation_id__header_absent__generates_a_value():
    request = make_request({})
    correlation_id = get_correlation_id(request)
    assert correlation_id
    assert correlation_id != get_correlation_id(make_request({}))


def test_get_user_agent__present_and_absent():
    assert get_user_agent(make_request({"User-Agent": "UA-Test"})) == "UA-Test"
    assert get_user_agent(make_request({})) == "unknown"
