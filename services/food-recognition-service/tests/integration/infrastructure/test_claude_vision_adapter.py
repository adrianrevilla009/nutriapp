"""ClaudeVisionAdapter -- against mocked/recorded HTTP responses only
(`httpx.MockTransport`), NEVER a live Anthropic API call (test-plan
section 2, implementation plan section 1's explicit requirement).

Fixture response bodies live in
tests/fixtures/claude_vision_responses/*.json -- hand-authored synthetic
JSON, never a real Anthropic API capture (test-plan section 7).
"""

from __future__ import annotations

import json
import os

import httpx
import pytest

from domain.ports.vision_recognition_port import VisionRecognitionUnavailableError
from infrastructure.external.claude_vision_adapter import ClaudeVisionAdapter

_FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "fixtures", "claude_vision_responses"
)


def _load_fixture(name: str) -> dict:
    with open(os.path.join(_FIXTURES_DIR, name)) as f:
        return json.load(f)


def _message_response(text: str) -> dict:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-4-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 100, "output_tokens": 40},
    }


def _adapter_with_transport(handler, fail_max: int = 5, reset_timeout_seconds: float = 0.2):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return ClaudeVisionAdapter(
        api_key="test-key",
        http_client=http_client,
        fail_max=fail_max,
        reset_timeout_seconds=reset_timeout_seconds,
    )


async def test_confident_response_parses_into_candidates():
    fixture = _load_fixture("confident_response.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_message_response(json.dumps(fixture)))

    adapter = _adapter_with_transport(handler)
    candidates = await adapter.analyze(b"\x89PNG\r\n\x1a\nfake")

    assert len(candidates) == 2
    assert candidates[0].name == "grilled chicken breast"
    assert candidates[0].portion_range.min_g == 120.0
    assert candidates[0].portion_range.max_g == 180.0
    assert candidates[0].confidence.value == 0.87
    assert adapter.model_version == "claude-haiku-4-5"
    await adapter.aclose()


async def test_malformed_json_response_is_a_parse_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_message_response("this is not JSON at all"))

    adapter = _adapter_with_transport(handler)
    with pytest.raises(VisionRecognitionUnavailableError):
        await adapter.analyze(b"fake-bytes")
    await adapter.aclose()


async def test_response_missing_required_fields_is_a_parse_failure():
    fixture = _load_fixture("malformed_missing_fields_response.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_message_response(json.dumps(fixture)))

    adapter = _adapter_with_transport(handler)
    with pytest.raises(VisionRecognitionUnavailableError):
        await adapter.analyze(b"fake-bytes")
    await adapter.aclose()


async def test_low_confidence_response_still_parses_candidates():
    fixture = _load_fixture("low_confidence_response.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_message_response(json.dumps(fixture)))

    adapter = _adapter_with_transport(handler)
    candidates = await adapter.analyze(b"fake-bytes")

    assert len(candidates) == 1
    assert candidates[0].confidence.value == 0.35
    await adapter.aclose()


async def test_5xx_retries_then_trips_circuit_breaker():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(500, json={"type": "error", "error": {"message": "boom"}})

    adapter = _adapter_with_transport(handler, fail_max=1)
    with pytest.raises(VisionRecognitionUnavailableError):
        await adapter.analyze(b"fake-bytes")
    # tenacity retries 3 attempts before the breaker records the failure.
    assert call_count["n"] == 3

    calls_before = call_count["n"]
    with pytest.raises(VisionRecognitionUnavailableError):
        await adapter.analyze(b"fake-bytes")
    # Circuit now open: fails fast, no new call reaches the transport.
    assert call_count["n"] == calls_before
    await adapter.aclose()


async def test_connection_error_raises_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    adapter = _adapter_with_transport(handler, fail_max=5)
    with pytest.raises(VisionRecognitionUnavailableError):
        await adapter.analyze(b"fake-bytes")
    await adapter.aclose()
