"""ConversationPort -- the LLM-provider adapter boundary
(.claude/agents/nutrition-assistant-agent.md: "the ... LLM provider [is an]
adapter behind ... ConversationPort"). Concrete adapter:
infrastructure.external.claude_conversation_adapter.ClaudeConversationAdapter,
structured directly on food-recognition-service's ClaudeVisionAdapter
resilience precedent (own circuit breaker, retry, timeouts, bulkhead)."""

from __future__ import annotations

from typing import Protocol


class ConversationUnavailableError(Exception):
    """Raised on circuit-open or a persistent provider failure. Callers
    must return a typed 'assistant temporarily unavailable' result, never
    an empty/garbage string presented as a real answer."""


class ConversationPort(Protocol):
    async def generate(self, prompt: str) -> str: ...
