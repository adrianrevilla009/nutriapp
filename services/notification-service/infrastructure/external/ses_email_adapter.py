"""SesEmailAdapter -- implements EmailProviderPort (ADR-0011: Amazon SES).
Talks to a configurable HTTP endpoint standing in for SES's send API --
in dev/CI this always points at SES sandbox mode or a local fake
(docs/notifications.md section 5), never real SES. Swapping the email
provider (e.g. to a different transactional-email vendor) means writing a
new adapter behind EmailProviderPort; nothing above this layer changes
(ADR-0001).

Resilience: own, dedicated purgatory circuit breaker (fail_max=5,
reset_timeout=30s), never shared with the SNS or identity-reveal
breakers. tenacity retry (3 attempts) only on transport-level failures --
an actual SES rejection (4xx) is a well-formed business response, not
retried. Own httpx.AsyncClient (bulkhead).
"""

from __future__ import annotations

import httpx
import purgatory
from purgatory.domain.model import OpenedState
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from domain.ports.email_provider_port import EmailProviderUnavailableError, EmailSendResult

CIRCUIT_NAME = "ses_email"
DEFAULT_FAIL_MAX = 5
DEFAULT_RESET_TIMEOUT_SECONDS = 30


class SesEmailAdapter:
    """Implements domain.ports.email_provider_port.EmailProviderPort."""

    def __init__(
        self,
        base_url: str,
        from_address: str,
        http_client: httpx.AsyncClient | None = None,
        fail_max: int = DEFAULT_FAIL_MAX,
        reset_timeout_seconds: float = DEFAULT_RESET_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._from_address = from_address
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
    async def _post(self, payload: dict[str, str]) -> httpx.Response:
        return await self._http.post(f"{self._base_url}/v2/email/outbound", json=payload)

    async def send(
        self, *, to: str, subject: str, html_body: str, correlation_id: str
    ) -> EmailSendResult:
        breaker = await self._breaker_factory.get_breaker(CIRCUIT_NAME)
        payload = {
            "from": self._from_address,
            "to": to,
            "subject": subject,
            "html_body": html_body,
            "correlation_id": correlation_id,
        }
        try:
            async with breaker:
                response = await self._post(payload)
                if response.status_code >= 500:
                    response.raise_for_status()
        except OpenedState as exc:
            raise EmailProviderUnavailableError("SES email circuit is open.") from exc
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            raise EmailProviderUnavailableError(f"SES send call failed: {exc}") from exc

        if response.status_code >= 400:
            raise EmailProviderUnavailableError(f"SES rejected the send ({response.status_code}).")

        body = response.json()
        return EmailSendResult(provider_message_id=body["message_id"])

    async def aclose(self) -> None:
        await self._http.aclose()
