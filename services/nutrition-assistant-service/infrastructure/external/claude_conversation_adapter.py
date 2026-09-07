"""ClaudeConversationAdapter -- implements ConversationPort using
Anthropic's Messages API (implementation plan section 4: "structured
directly on food-recognition-service's ClaudeVisionAdapter precedent").

Model tier (.claude/skills/llm-cost-and-model-selection/SKILL.md,
implementation plan section 9 resolution 5): starts on **Claude Haiku
4.5** (DEFAULT_MODEL) -- the smallest/cheapest tier expected to meet the
accuracy bar, mirroring food-recognition-service's ClaudeVisionAdapter
precedent exactly. Configurable via NUTRITION_ASSISTANT_SERVICE_CONVERSATION_MODEL
(never hardcoded past this constant) so an operator can react to a real
evaluation result (tests/evaluation/fixed_eval_set.py) without a code
change -- escalating tiers is still a decision to be justified against
that evaluation set, not a silent config bump.

The full prompt (system instructions + retrieved context + chat history +
query) is assembled by domain.services.prompt_assembler.assemble_prompt
BEFORE this adapter is ever called -- this adapter's only job is the
resilient wire call, it does no prompt construction of its own. See
infrastructure/prompts/system_prompt_v1.md for the versioned,
human-reviewable copy of the system-instruction text embedded in
prompt_assembler.py (duplicated deliberately: the domain layer must stay
I/O-free per hexagonal-architecture SKILL.md, so the runtime source of
truth is the Python constant, not a file read at request time -- flagged
for architecture-agent review as a minor tension with
prompt-engineering-standards SKILL.md's literal preference for a
file-backed prompt).

Resilience (resilience-patterns SKILL.md): a DEDICATED purgatory circuit
breaker (fail_max=5, reset_timeout=30s, same starting default as
claude_vision), a tenacity retry (3 attempts, exponential backoff+jitter,
transient connection/timeout/5xx errors only), and an explicit timeout
(5s connect / 30s read -- a conversational generation call is expected to
take longer than a single vision classification call). Own, isolated
anthropic.AsyncAnthropic client/connection pool (bulkhead)."""

from __future__ import annotations

import anthropic
import httpx
import purgatory
from purgatory.domain.model import OpenedState
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from domain.ports.conversation_port import ConversationUnavailableError

CIRCUIT_NAME = "claude_conversation"
DEFAULT_FAIL_MAX = 5
DEFAULT_RESET_TIMEOUT_SECONDS = 30
DEFAULT_MODEL = "claude-haiku-4-5"
DEFAULT_MAX_TOKENS = 1024

SYSTEM_PROMPT_VERSION = "v1"


class ClaudeConversationAdapter:
    """Implements domain.ports.conversation_port.ConversationPort."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        http_client: httpx.AsyncClient | None = None,
        fail_max: int = DEFAULT_FAIL_MAX,
        reset_timeout_seconds: float = DEFAULT_RESET_TIMEOUT_SECONDS,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key,
            http_client=http_client,
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0),
            max_retries=0,  # tenacity handles retries explicitly below, not the SDK's own
        )
        self._breaker_factory = purgatory.AsyncCircuitBreakerFactory(
            default_threshold=fail_max, default_ttl=reset_timeout_seconds
        )

    @property
    def model_version(self) -> str:
        return self._model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=5.0),
        retry=retry_if_exception_type(
            (anthropic.APIConnectionError, anthropic.APITimeoutError, anthropic.InternalServerError)
        ),
        reraise=True,
    )
    async def _call(self, prompt: str) -> anthropic.types.Message:
        return await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

    async def generate(self, prompt: str) -> str:
        breaker = await self._breaker_factory.get_breaker(CIRCUIT_NAME)
        try:
            async with breaker:
                message = await self._call(prompt)
        except OpenedState as exc:
            raise ConversationUnavailableError("Claude conversation circuit is open.") from exc
        except anthropic.APIStatusError as exc:
            raise ConversationUnavailableError(f"Claude conversation API error: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise ConversationUnavailableError(
                f"Claude conversation connection error: {exc}"
            ) from exc

        try:
            block = message.content[0]
            return block.text  # type: ignore[union-attr]
        except (AttributeError, IndexError) as exc:
            raise ConversationUnavailableError(
                f"Claude conversation response could not be parsed: {exc}"
            ) from exc

    async def aclose(self) -> None:
        await self._client.close()
