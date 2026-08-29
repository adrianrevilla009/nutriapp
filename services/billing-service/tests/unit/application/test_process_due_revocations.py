import uuid
from datetime import datetime, timedelta, timezone

from application.commands.process_due_revocations import (
    ProcessDueRevocationsCommand,
    ProcessDueRevocationsHandler,
)
from domain.ports.entitlement_revocation_schedule_repository_port import RevocationScheduleEntry
from tests.fixtures.factories import (
    FakeEntitlementRevocationScheduleRepository,
    FakeOutboxRepository,
)

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


async def test_due_row_is_processed_and_published():
    due_user = uuid.uuid4()
    seed = [
        RevocationScheduleEntry(
            user_id=due_user, revoke_at=NOW - timedelta(hours=1), processed=False
        )
    ]
    revocation_schedule = FakeEntitlementRevocationScheduleRepository(seed=seed)
    outbox = FakeOutboxRepository()
    handler = ProcessDueRevocationsHandler(revocation_schedule, outbox, now_fn=lambda: NOW)

    count = await handler.handle(ProcessDueRevocationsCommand(correlation_id="corr-8"))

    assert count == 1
    assert [e.event_type for e in outbox.enqueued] == ["EntitlementRevoked"]
    assert outbox.enqueued[0].payload["user_id"] == str(due_user)
    assert revocation_schedule.by_user[due_user].processed is True


async def test_not_yet_due_row_is_left_alone():
    future_user = uuid.uuid4()
    seed = [
        RevocationScheduleEntry(
            user_id=future_user, revoke_at=NOW + timedelta(days=1), processed=False
        )
    ]
    revocation_schedule = FakeEntitlementRevocationScheduleRepository(seed=seed)
    outbox = FakeOutboxRepository()
    handler = ProcessDueRevocationsHandler(revocation_schedule, outbox, now_fn=lambda: NOW)

    count = await handler.handle(ProcessDueRevocationsCommand(correlation_id="corr-9"))

    assert count == 0
    assert outbox.enqueued == []
    assert revocation_schedule.by_user[future_user].processed is False


async def test_revoke_at_exactly_now_is_due():
    """`list_due` uses an inclusive `revoke_at <= now` comparison -- at
    exactly the boundary instant, revocation IS due (qa-agent: pin the
    boundary explicitly; consistency check against
    `Subscription.is_entitled`'s own boundary, which is exclusive on the
    other side -- `now < current_period_end` -- so the two are
    complementary, never both true/both false at the same instant)."""
    boundary_user = uuid.uuid4()
    seed = [RevocationScheduleEntry(user_id=boundary_user, revoke_at=NOW, processed=False)]
    revocation_schedule = FakeEntitlementRevocationScheduleRepository(seed=seed)
    outbox = FakeOutboxRepository()
    handler = ProcessDueRevocationsHandler(revocation_schedule, outbox, now_fn=lambda: NOW)

    count = await handler.handle(ProcessDueRevocationsCommand(correlation_id="corr-boundary"))

    assert count == 1
    assert revocation_schedule.by_user[boundary_user].processed is True


async def test_already_processed_row_is_not_reprocessed():
    processed_user = uuid.uuid4()
    seed = [
        RevocationScheduleEntry(
            user_id=processed_user, revoke_at=NOW - timedelta(days=1), processed=True
        )
    ]
    revocation_schedule = FakeEntitlementRevocationScheduleRepository(seed=seed)
    outbox = FakeOutboxRepository()
    handler = ProcessDueRevocationsHandler(revocation_schedule, outbox, now_fn=lambda: NOW)

    count = await handler.handle(ProcessDueRevocationsCommand(correlation_id="corr-10"))

    assert count == 0
    assert outbox.enqueued == []
