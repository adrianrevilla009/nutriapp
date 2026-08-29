"""SnsPushAdapter -- implements PushProviderPort (ADR-0011: Amazon SNS,
or FCM/APNs directly). Talks to a configurable HTTP endpoint standing in
for SNS's publish API -- in dev/CI this always points at a local fake
push endpoint (docs/notifications.md section 5), never a real device.

Resilience: own, dedicated purgatory circuit breaker (fail_max=5,
reset_timeout=30s), never shared with the SES or identity-reveal
breakers. tenacity retry (3 attempts) only on transport-level failures.
Own httpx.AsyncClient (bulkhead).
"""

from __future__ import annotations

from collections.abc import Mapping

import httpx
import purgatory
from purgatory.domain.model import OpenedState
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from domain.ports.push_provider_port import PushProviderUnavailableError, PushSendResult

CIRCUIT_NAME = "sns_push"
DEFAULT_FAIL_MAX = 5
DEFAULT_RESET_TIMEOUT_SECONDS = 30


class SnsPushAdapter:
    """Implements domain.ports.push_provider_port.PushProviderPort."""

    def __init__(
        self,
        base_url: str,
        http_client: httpx.AsyncClient | None = None,
        fail_max: int = DEFAULT_FAIL_MAX,
        reset_timeout_seconds: float = DEFAULT_RESET_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(connect=2.0, read=5.0, write=2.0, pool=2.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        self._breaker_factory = purgatory.AsyncCircuitBreakerFactory(
            default_threshold=fail_max, default_ttl=reset_timeout_seconds
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.2, max=2.0),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def _post(self, payload: dict[str, object]) -> httpx.Response:
        return await self._http.post(f"{self._base_url}/v1/push/publish", json=payload)

    async def send(
        self,
        *,
        device_token: str,
        title: str,
        body: str,
        data: Mapping[str, str],
        correlation_id: str,
    ) -> PushSendResult:
        breaker = await self._breaker_factory.get_breaker(CIRCUIT_NAME)
        payload: dict[str, object] = {
            "device_token": device_token,
            "title": title,
            "body": body,
            "data": dict(data),
            "correlation_id": correlation_id,
        }
        try:
            async with breaker:
                response = await self._post(payload)
                if response.status_code >= 500:
                    response.raise_for_status()
        except OpenedState as exc:
            raise PushProviderUnavailableError("SNS push circuit is open.") from exc
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            raise PushProviderUnavailableError(f"SNS publish call failed: {exc}") from exc

        if response.status_code >= 400:
            raise PushProviderUnavailableError(
                f"SNS rejected the publish ({response.status_code})."
            )

        response_body = response.json()
        return PushSendResult(provider_message_id=response_body["message_id"])

    async def aclose(self) -> None:
        await self._http.aclose()
