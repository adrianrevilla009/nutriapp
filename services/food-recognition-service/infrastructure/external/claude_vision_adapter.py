"""ClaudeVisionAdapter -- implements VisionRecognitionPort using
Anthropic's Messages API with an image content block (implementation plan
section 1's technology choice: a multimodal Claude vision call, not a
custom-trained model).

Model tier (`.claude/skills/llm-cost-and-model-selection/SKILL.md`):
starts on **Claude Haiku 4.5** (`DEFAULT_MODEL`) -- the smallest/cheapest
tier expected to meet the accuracy bar, per that skill's "prefer the
smallest/cheapest model" rule. Configurable via
`FOOD_RECOGNITION_VISION_MODEL` (never hardcoded past this constant) so an
operator can react to a real evaluation result without a code change;
escalating tiers is still an ADR-worthy decision (implementation plan
section 1), this config knob only controls which already-approved string
is sent.

Prompt (`.claude/skills/prompt-engineering-standards/SKILL.md` -- prompts
are versioned/reviewed like code): `SYSTEM_PROMPT_VERSION` below. The
prompt requests STRICT JSON only and stays within "identify the food and
estimate its portion" -- it explicitly does not ask for a health/dietary
judgement (implementation plan section 6(d)).

Structured-output parsing: a malformed/unparseable response is ALWAYS
treated as a total detection failure (`VisionRecognitionUnavailableError`)
-- never a partial/best-effort parse (implementation plan section 4).

Resilience (`.claude/skills/resilience-patterns/SKILL.md`): a DEDICATED
`purgatory` circuit breaker (`fail_max=5`, `reset_timeout=30s`), a
`tenacity` retry (3 attempts, exponential backoff+jitter, transient
connection/timeout errors only -- a vision analysis call is a read with no
side effect, safe to retry), and an explicit timeout (5s connect / 20s
read). Own, isolated `anthropic.AsyncAnthropic` client/connection pool
(bulkhead).
"""

from __future__ import annotations

import base64
import json
from typing import Any

import anthropic
import httpx
import purgatory
from purgatory.domain.model import OpenedState
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from domain.ports.vision_recognition_port import VisionRecognitionUnavailableError
from domain.value_objects.confidence_score import ConfidenceScore
from domain.value_objects.food_candidate import FoodCandidate
from domain.value_objects.portion_range_grams import PortionRangeGrams

CIRCUIT_NAME = "claude_vision"
DEFAULT_FAIL_MAX = 5
DEFAULT_RESET_TIMEOUT_SECONDS = 30
DEFAULT_MODEL = "claude-haiku-4-5"
DEFAULT_MAX_TOKENS = 1024

SYSTEM_PROMPT_VERSION = "v1"
SYSTEM_PROMPT = (
    "You are a food-identification assistant. You are shown one photo of a "
    "plate, container, or package of food. Identify up to 3 distinct food "
    "items visible. For EACH item, provide: its common name, an estimated "
    "portion-size RANGE in grams (min_g and max_g, min_g strictly less than "
    "max_g -- never a single exact number, since a photo can only support an "
    "approximate estimate), and a confidence score between 0.0 and 1.0 for "
    "how sure you are of the identification. "
    "Respond with STRICT JSON ONLY, no markdown, no other text, matching "
    'exactly this shape: {"candidates": [{"name": "string", '
    '"portion_range_min_g": number, "portion_range_max_g": number, '
    '"confidence": number}]}. '
    "Identify the food and estimate its portion only. Do not comment on "
    "whether the food is healthy or unhealthy, do not give dietary or "
    "nutritional advice, and do not diagnose or suggest any medical "
    "condition -- that is strictly out of scope for this task."
)

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"


def _detect_media_type(image_bytes: bytes) -> str:
    if image_bytes.startswith(_PNG_SIGNATURE):
        return "image/png"
    if image_bytes.startswith(_JPEG_SIGNATURE):
        return "image/jpeg"
    return "image/webp"


def _parse_candidates(message: anthropic.types.Message) -> list[FoodCandidate]:
    try:
        block = message.content[0]
        text = block.text  # type: ignore[union-attr]
        data: dict[str, Any] = json.loads(text)
        raw_candidates = data["candidates"]
        candidates: list[FoodCandidate] = []
        for raw in raw_candidates:
            candidates.append(
                FoodCandidate(
                    name=str(raw["name"]),
                    portion_range=PortionRangeGrams(
                        min_g=float(raw["portion_range_min_g"]),
                        max_g=float(raw["portion_range_max_g"]),
                    ),
                    confidence=ConfidenceScore(float(raw["confidence"])),
                )
            )
        return candidates
    except (
        AttributeError,
        IndexError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise VisionRecognitionUnavailableError(
            f"Claude vision response could not be parsed: {exc}"
        ) from exc


class ClaudeVisionAdapter:
    """Implements domain.ports.vision_recognition_port.VisionRecognitionPort."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        http_client: httpx.AsyncClient | None = None,
        fail_max: int = DEFAULT_FAIL_MAX,
        reset_timeout_seconds: int = DEFAULT_RESET_TIMEOUT_SECONDS,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key,
            http_client=http_client,
            timeout=httpx.Timeout(connect=5.0, read=20.0, write=5.0, pool=5.0),
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
    async def _call(self, image_bytes: bytes, media_type: str) -> anthropic.types.Message:
        image_b64 = base64.standard_b64encode(image_bytes).decode("ascii")
        # Anthropic's typed `MessageParam`/content-block unions are a large
        # discriminated union that mypy strict cannot narrow from a plain
        # dict literal -- `Any` here is the request payload only, not a
        # weakening of this adapter's own return-type contract (still
        # `anthropic.types.Message`, still narrowed to `FoodCandidate` by
        # `_parse_candidates` before it ever reaches the application layer).
        messages: Any = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": "Identify the food item(s) in this photo."},
                ],
            }
        ]
        return await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=SYSTEM_PROMPT,
            messages=messages,
        )

    async def analyze(self, image_bytes: bytes) -> list[FoodCandidate]:
        breaker = await self._breaker_factory.get_breaker(CIRCUIT_NAME)
        media_type = _detect_media_type(image_bytes)
        try:
            async with breaker:
                message = await self._call(image_bytes, media_type)
        except OpenedState as exc:
            raise VisionRecognitionUnavailableError("Claude vision circuit is open.") from exc
        except anthropic.APIStatusError as exc:
            raise VisionRecognitionUnavailableError(f"Claude vision API error: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise VisionRecognitionUnavailableError(
                f"Claude vision connection error: {exc}"
            ) from exc

        return _parse_candidates(message)

    async def aclose(self) -> None:
        await self._client.close()
