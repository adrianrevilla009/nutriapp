"""OutboxRelayWorker -- scaffold-doesn't-silently-break smoke test only
(test plan section 3: "no live publisher wired to it this pass"). Uses a
no-op fake publisher against a real (empty) Postgres outbox table."""

from __future__ import annotations

from infrastructure.messaging.outbox_relay_worker import OutboxRelayWorker


class _NoOpPublisher:
    def __init__(self) -> None:
        self.publish_calls = 0

    async def publish(self, event) -> None:
        self.publish_calls += 1


async def test_relay_once_against_an_empty_outbox_does_not_error(session_factory) -> None:
    publisher = _NoOpPublisher()
    worker = OutboxRelayWorker(session_factory, publisher)
    relayed_count = await worker.relay_once()
    assert relayed_count == 0
    assert publisher.publish_calls == 0
