from datetime import datetime, timedelta, timezone

from domain.value_objects.subscription_status import SubscriptionStatus
from tests.fixtures.factories import make_subscription

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def test_start_creates_active_not_cancel_at_period_end():
    sub = make_subscription(status=SubscriptionStatus.active(), cancel_at_period_end=False)
    assert sub.status == SubscriptionStatus.active()
    assert sub.cancel_at_period_end is False


def test_cancel_sets_cancel_at_period_end_but_not_status():
    sub = make_subscription(status=SubscriptionStatus.active(), cancel_at_period_end=False)
    cancelled = sub.cancel(NOW)
    assert cancelled.cancel_at_period_end is True
    assert cancelled.status == SubscriptionStatus.active()
    assert cancelled.updated_at == NOW


def test_cancel_is_idempotent():
    sub = make_subscription(status=SubscriptionStatus.active(), cancel_at_period_end=True)
    cancelled_again = sub.cancel(NOW)
    assert cancelled_again.cancel_at_period_end is True
    assert cancelled_again.status == SubscriptionStatus.active()


def test_mark_past_due():
    sub = make_subscription(status=SubscriptionStatus.active())
    past_due = sub.mark_past_due(NOW)
    assert past_due.status == SubscriptionStatus.past_due()
    assert past_due.updated_at == NOW


def test_renew_extends_period_and_clears_past_due():
    sub = make_subscription(status=SubscriptionStatus.past_due(), cancel_at_period_end=False)
    new_period_end = NOW + timedelta(days=30)
    renewed = sub.renew(current_period_end=new_period_end, now=NOW)
    assert renewed.status == SubscriptionStatus.active()
    assert renewed.current_period_end == new_period_end
    assert renewed.cancel_at_period_end is False


def test_is_entitled_active_subscription():
    sub = make_subscription(status=SubscriptionStatus.active(), cancel_at_period_end=False)
    assert sub.is_entitled(NOW) is True


def test_is_entitled_past_due_still_entitled():
    sub = make_subscription(status=SubscriptionStatus.past_due(), cancel_at_period_end=False)
    assert sub.is_entitled(NOW) is True


def test_is_entitled_cancel_at_period_end_before_period_end():
    period_end = NOW + timedelta(days=5)
    sub = make_subscription(
        status=SubscriptionStatus.active(), cancel_at_period_end=True, current_period_end=period_end
    )
    assert sub.is_entitled(NOW) is True


def test_is_entitled_cancel_at_period_end_after_period_end():
    period_end = NOW - timedelta(days=1)
    sub = make_subscription(
        status=SubscriptionStatus.active(), cancel_at_period_end=True, current_period_end=period_end
    )
    assert sub.is_entitled(NOW) is False


def test_is_entitled_canceled_status_never_entitled():
    sub = make_subscription(status=SubscriptionStatus.canceled(), cancel_at_period_end=False)
    assert sub.is_entitled(NOW) is False


def test_is_entitled_at_exact_period_end_boundary_not_entitled():
    """`is_entitled` uses a strict `now < current_period_end` comparison --
    at exactly the boundary instant, access has ended (qa-agent: pin the
    boundary explicitly, don't rely on off-by-one luck)."""
    sub = make_subscription(
        status=SubscriptionStatus.active(), cancel_at_period_end=True, current_period_end=NOW
    )
    assert sub.is_entitled(NOW) is False


def test_correct_period_end_replaces_only_period_end():
    sub = make_subscription(
        status=SubscriptionStatus.active(),
        cancel_at_period_end=False,
        current_period_end=NOW + timedelta(days=30),
    )
    real_period_end = NOW + timedelta(days=31)
    corrected = sub.correct_period_end(real_period_end, NOW)

    assert corrected.current_period_end == real_period_end
    assert corrected.updated_at == NOW
    assert corrected.status == sub.status
    assert corrected.cancel_at_period_end == sub.cancel_at_period_end
    assert corrected.subscription_id == sub.subscription_id
    assert corrected.created_at == sub.created_at
