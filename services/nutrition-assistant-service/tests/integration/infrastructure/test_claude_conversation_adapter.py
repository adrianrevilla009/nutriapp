"""ClaudeConversationAdapter -- against mocked HTTP responses only
(httpx.MockTransport), NEVER a live Anthropic API call (test plan section
3's explicit "circuit-breaker matrix" requirement, mirrors
food-recognition-service's ClaudeVisionAdapter test precedent exactly)."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from domain.ports.conversation_port import ConversationUnavailableError
from infrastructure.external.claude_conversation_adapter import ClaudeConversationAdapter


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
    return ClaudeConversationAdapter(
        api_key="test-key",
        http_client=http_client,
        fail_max=fail_max,
        reset_timeout_seconds=reset_timeout_seconds,
    )


async def test_successful_response_returns_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_message_response("Here is your answer."))

    adapter = _adapter_with_transport(handler)
    result = await adapter.generate("what did I eat")
    assert result == "Here is your answer."
    assert adapter.model_version == "claude-haiku-4-5"
    await adapter.aclose()


async def test_5xx_retries_three_times_then_raises_unavailable() -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(500, json={"type": "error", "error": {"message": "boom"}})

    adapter = _adapter_with_transport(handler, fail_max=5)
    with pytest.raises(ConversationUnavailableError):
        await adapter.generate("q")
    assert call_count["n"] == 3  # tenacity's 3 attempts before the breaker records failure
    await adapter.aclose()


async def test_circuit_opens_after_fail_max_and_fails_fast() -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(500, json={"type": "error", "error": {"message": "boom"}})

    adapter = _adapter_with_transport(handler, fail_max=1, reset_timeout_seconds=5.0)
    with pytest.raises(ConversationUnavailableError):
        await adapter.generate("q")
    calls_before = call_count["n"]

    with pytest.raises(ConversationUnavailableError):
        await adapter.generate("q")
    assert call_count["n"] == calls_before  # circuit open -- no new network attempt
    await adapter.aclose()


async def test_circuit_recovers_after_reset_timeout() -> None:
    state = {"fail": True, "calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["calls"] += 1
        if state["fail"]:
            return httpx.Response(500, json={"type": "error", "error": {"message": "boom"}})
        return httpx.Response(200, json=_message_response("recovered"))

    adapter = _adapter_with_transport(handler, fail_max=1, reset_timeout_seconds=0.05)
    with pytest.raises(ConversationUnavailableError):
        await adapter.generate("q")  # trips the breaker

    await asyncio.sleep(0.1)  # exceed reset_timeout_seconds
    state["fail"] = False
    result = await adapter.generate("q")  # half-open trial call succeeds -> closes circuit
    assert result == "recovered"
    await adapter.aclose()


async def test_connection_error_raises_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    adapter = _adapter_with_transport(handler, fail_max=5)
    with pytest.raises(ConversationUnavailableError):
        await adapter.generate("q")
    await adapter.aclose()


async def test_timeout_counts_as_a_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    adapter = _adapter_with_transport(handler, fail_max=5)
    with pytest.raises(ConversationUnavailableError):
        await adapter.generate("q")
    await adapter.aclose()


async def test_malformed_response_body_raises_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"id": "msg", "type": "message", "role": "assistant", "content": []}
        )

    adapter = _adapter_with_transport(handler)
    with pytest.raises(ConversationUnavailableError):
        await adapter.generate("q")
    await adapter.aclose()
