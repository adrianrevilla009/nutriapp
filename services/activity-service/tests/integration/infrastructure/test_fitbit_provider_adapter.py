"""FitbitProviderAdapter -- against mocked HTTP responses only
(`httpx.MockTransport`), NEVER a live Fitbit API call. Implements
`/plans/activity-service/test-plan.md`'s 2026-09-11 addendum, sections 2
and 3.

No real Fitbit developer account exists in this environment -- every
response body below is hand-authored synthetic JSON shaped to match
Fitbit's publicly documented contract, never a real capture, same
convention as `test_claude_vision_adapter.py` /
`test_stripe_payment_adapter.py`.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from domain.ports.wearable_provider_port import (
    WearableConnectionNotFoundError,
    WearableProviderUnavailableError,
)
from domain.value_objects.wearable_oauth_tokens import WearableOAuthTokens
from infrastructure.external.fitbit_provider_adapter import FitbitProviderAdapter
from infrastructure.external.in_memory_wearable_token_store import InMemoryWearableTokenStore

CLIENT_ID = "test-client-id"
CLIENT_SECRET = "test-client-secret"
REDIRECT_URI = "https://app.nutriapp.test/wearables/fitbit/callback"


def _token_response(*, access="access-token-1", refresh="refresh-token-1", expires_in=3600):
    return {
        "access_token": access,
        "refresh_token": refresh,
        "expires_in": expires_in,
        "token_type": "Bearer",
        "user_id": "ABC123",
        "scope": "activity",
    }


def _activities_response(activities):
    return {"activities": activities, "pagination": {}}


def _activity(
    *, log_id=1, name="Run", duration_ms=1_800_000, calories=312, started_at="2026-09-10T07:00:00"
):
    return {
        "logId": log_id,
        "activityName": name,
        "name": name,
        "duration": duration_ms,
        "calories": calories,
        "startTime": started_at,
    }


def _adapter(handler, *, token_store=None, fail_max=5, reset_timeout_seconds=0.2):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return FitbitProviderAdapter(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        token_store=token_store or InMemoryWearableTokenStore(),
        http_client=http_client,
        fail_max=fail_max,
        reset_timeout_seconds=reset_timeout_seconds,
    )


def _expected_basic_auth() -> str:
    raw = f"{CLIENT_ID}:{CLIENT_SECRET}".encode()
    return f"Basic {base64.b64encode(raw).decode('ascii')}"


USER = uuid.uuid4()


# ---------------------------------------------------------------------------
# connect() -- OAuth token exchange
# ---------------------------------------------------------------------------


async def test_connect_success_persists_tokens_via_token_store():
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(200, json=_token_response())

    store = InMemoryWearableTokenStore()
    adapter = _adapter(handler, token_store=store)

    await adapter.connect(USER, "one-time-auth-code")

    assert len(seen_requests) == 1
    request = seen_requests[0]
    assert request.url.path == "/oauth2/token"
    assert request.headers["Authorization"] == _expected_basic_auth()
    body = request.content.decode("utf-8")
    assert "grant_type=authorization_code" in body
    assert "code=one-time-auth-code" in body

    stored = await store.get(USER, "fitbit")
    assert stored is not None
    assert stored.access_token == "access-token-1"
    await adapter.aclose()


async def test_connect_rejected_grant_raises_and_persists_nothing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"errors": [{"errorType": "invalid_grant"}]})

    store = InMemoryWearableTokenStore()
    adapter = _adapter(handler, token_store=store)

    with pytest.raises(WearableProviderUnavailableError):
        await adapter.connect(USER, "already-used-code")

    assert await store.get(USER, "fitbit") is None
    await adapter.aclose()


async def test_connect_transport_failure_is_never_retried():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        raise httpx.ConnectError("boom", request=request)

    adapter = _adapter(handler, fail_max=5)

    with pytest.raises(WearableProviderUnavailableError):
        await adapter.connect(USER, "some-code")

    # Single-use grant -- exactly one outbound attempt, never a tenacity retry.
    assert call_count["n"] == 1
    await adapter.aclose()


async def test_connect_circuit_breaker_opens_after_fail_max_then_fails_fast():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        # A raised transport exception, not a 4xx/5xx *response* -- only an
        # exception inside the breaker's `async with` block counts as a
        # breaker failure (a non-2xx httpx.Response is handled separately,
        # after the breaker context has already exited successfully).
        raise httpx.ConnectError("boom", request=request)

    adapter = _adapter(handler, fail_max=5, reset_timeout_seconds=30)

    for _ in range(5):
        with pytest.raises(WearableProviderUnavailableError):
            await adapter.connect(USER, "code")
    assert call_count["n"] == 5

    # 6th call: circuit open, fails fast, no new outbound request.
    with pytest.raises(WearableProviderUnavailableError):
        await adapter.connect(USER, "code")
    assert call_count["n"] == 5
    await adapter.aclose()


async def test_connect_read_timeout_raises_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    adapter = _adapter(handler)

    with pytest.raises(WearableProviderUnavailableError):
        await adapter.connect(USER, "code")
    await adapter.aclose()


# ---------------------------------------------------------------------------
# Token refresh (exercised via sync()/disconnect() with an expired token)
# ---------------------------------------------------------------------------


async def _store_with_expired_token(user=USER) -> InMemoryWearableTokenStore:
    store = InMemoryWearableTokenStore()
    await store.save(
        user,
        "fitbit",
        WearableOAuthTokens(
            access_token="stale-access",
            refresh_token="stale-refresh",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        ),
    )
    return store


async def test_sync_refreshes_expired_token_and_rotates_refresh_token():
    requests_seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        if request.url.path == "/oauth2/token":
            return httpx.Response(
                200, json=_token_response(access="fresh-access", refresh="fresh-refresh")
            )
        assert request.url.path == "/1/user/-/activities/list.json"
        return httpx.Response(200, json=_activities_response([]))

    store = await _store_with_expired_token()
    adapter = _adapter(handler, token_store=store)

    results = await adapter.sync(USER, since=datetime.now(timezone.utc) - timedelta(days=1))

    assert results == []
    refresh_request = requests_seen[0]
    assert refresh_request.url.path == "/oauth2/token"
    assert "grant_type=refresh_token" in refresh_request.content.decode("utf-8")
    assert "stale-refresh" in refresh_request.content.decode("utf-8")

    stored = await store.get(USER, "fitbit")
    assert stored is not None
    assert stored.access_token == "fresh-access"
    assert stored.refresh_token == "fresh-refresh"
    await adapter.aclose()


async def test_refresh_transport_failure_is_never_retried():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        raise httpx.ConnectError("boom", request=request)

    store = await _store_with_expired_token()
    adapter = _adapter(handler, token_store=store, fail_max=5)

    with pytest.raises(WearableProviderUnavailableError):
        await adapter.sync(USER, since=datetime.now(timezone.utc))

    assert call_count["n"] == 1
    await adapter.aclose()


async def test_sync_with_no_stored_connection_raises_without_network_call():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json=_activities_response([]))

    adapter = _adapter(handler)

    with pytest.raises(WearableConnectionNotFoundError):
        await adapter.sync(USER, since=datetime.now(timezone.utc))

    assert call_count["n"] == 0
    await adapter.aclose()


# ---------------------------------------------------------------------------
# sync() -- activity fetch
# ---------------------------------------------------------------------------


async def _store_with_fresh_token(user=USER) -> InMemoryWearableTokenStore:
    store = InMemoryWearableTokenStore()
    await store.save(
        user,
        "fitbit",
        WearableOAuthTokens(
            access_token="fresh-access",
            refresh_token="fresh-refresh",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ),
    )
    return store


async def test_sync_parses_activities_into_wearable_sync_results():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer fresh-access"
        return httpx.Response(
            200,
            json=_activities_response(
                [
                    _activity(log_id=1, name="Run", duration_ms=1_800_000, calories=312),
                    _activity(
                        log_id=2,
                        name="Bike",
                        duration_ms=900_000,
                        calories=180,
                        started_at="2026-09-11T08:00:00",
                    ),
                ]
            ),
        )

    store = await _store_with_fresh_token()
    adapter = _adapter(handler, token_store=store)

    results = await adapter.sync(USER, since=datetime.now(timezone.utc) - timedelta(days=1))

    assert len(results) == 2
    assert results[0].provider_activity_id == "1"
    assert int(results[0].duration) == 30
    assert float(results[0].calories_burned) == 312.0
    assert results[1].provider_activity_id == "2"
    assert int(results[1].duration) == 15
    await adapter.aclose()


async def test_sync_unrecognized_activity_name_maps_to_other_with_label():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_activities_response(
                [_activity(log_id=9, name="Pilates", duration_ms=600_000, calories=90)]
            ),
        )

    store = await _store_with_fresh_token()
    adapter = _adapter(handler, token_store=store)

    results = await adapter.sync(USER, since=datetime.now(timezone.utc))

    assert len(results) == 1
    from domain.value_objects.exercise_type import ExerciseType

    assert results[0].exercise_type is ExerciseType.OTHER
    assert results[0].label == "Pilates"
    await adapter.aclose()


async def test_sync_empty_activities_returns_empty_list_not_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_activities_response([]))

    store = await _store_with_fresh_token()
    adapter = _adapter(handler, token_store=store)

    results = await adapter.sync(USER, since=datetime.now(timezone.utc))

    assert results == []
    await adapter.aclose()


async def test_sync_transient_transport_failure_is_retried_three_times():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        raise httpx.ConnectError("boom", request=request)

    store = await _store_with_fresh_token()
    adapter = _adapter(handler, token_store=store, fail_max=5)

    with pytest.raises(WearableProviderUnavailableError):
        await adapter.sync(USER, since=datetime.now(timezone.utc))

    assert call_count["n"] == 3
    await adapter.aclose()


async def test_sync_circuit_breaker_is_dedicated_and_separate_from_oauth_breaker():
    connect_calls = {"n": 0}
    sync_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/token":
            connect_calls["n"] += 1
            return httpx.Response(200, json=_token_response())
        sync_calls["n"] += 1
        raise httpx.ConnectError("boom", request=request)

    store = await _store_with_fresh_token()
    adapter = _adapter(handler, token_store=store, fail_max=1, reset_timeout_seconds=30)

    # Trip the sync-only breaker.
    with pytest.raises(WearableProviderUnavailableError):
        await adapter.sync(USER, since=datetime.now(timezone.utc))
    assert sync_calls["n"] == 3  # tenacity's 3 retry attempts before the breaker records failure.

    with pytest.raises(WearableProviderUnavailableError):
        await adapter.sync(USER, since=datetime.now(timezone.utc))
    assert sync_calls["n"] == 3  # circuit open: fails fast, no new attempt.

    # OAuth breaker is untouched -- connect() still goes through.
    await adapter.connect(USER, "some-code")
    assert connect_calls["n"] == 1
    await adapter.aclose()


# ---------------------------------------------------------------------------
# disconnect()
# ---------------------------------------------------------------------------


async def test_disconnect_clears_local_state_even_when_revoke_call_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/oauth2/revoke"
        return httpx.Response(500, json={"errors": []})

    store = await _store_with_fresh_token()
    adapter = _adapter(handler, token_store=store)

    await adapter.disconnect(USER)

    assert await store.get(USER, "fitbit") is None
    with pytest.raises(WearableConnectionNotFoundError):
        await adapter.sync(USER, since=datetime.now(timezone.utc))
    await adapter.aclose()


async def test_disconnect_clears_local_state_when_revoke_call_succeeds():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    store = await _store_with_fresh_token()
    adapter = _adapter(handler, token_store=store)

    await adapter.disconnect(USER)

    assert await store.get(USER, "fitbit") is None
    with pytest.raises(WearableConnectionNotFoundError):
        await adapter.sync(USER, since=datetime.now(timezone.utc))
    await adapter.aclose()


async def test_disconnect_with_no_stored_connection_is_idempotent_no_op():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json={})

    adapter = _adapter(handler)

    await adapter.disconnect(USER)  # No error raised.

    assert call_count["n"] == 0
    await adapter.aclose()


async def test_disconnect_called_twice_is_idempotent():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    store = await _store_with_fresh_token()
    adapter = _adapter(handler, token_store=store)

    await adapter.disconnect(USER)
    await adapter.disconnect(USER)  # second call: no error, no stored record either way.

    assert await store.get(USER, "fitbit") is None
    await adapter.aclose()


# ---------------------------------------------------------------------------
# Idempotency of sync() as a pure read
# ---------------------------------------------------------------------------


async def test_sync_replayed_with_same_since_returns_same_results_both_times():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_activities_response(
                [_activity(log_id=42, name="Run", duration_ms=1_800_000, calories=312)]
            ),
        )

    store = await _store_with_fresh_token()
    adapter = _adapter(handler, token_store=store)

    since = datetime.now(timezone.utc) - timedelta(days=1)
    first = await adapter.sync(USER, since=since)
    second = await adapter.sync(USER, since=since)

    assert first == second
    await adapter.aclose()
