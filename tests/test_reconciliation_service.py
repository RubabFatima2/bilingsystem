"""Unit tests for the reconciliation background job (retries + sync)."""

from types import SimpleNamespace
from uuid import uuid4

from app.constants.subscription_status import SubscriptionStatus
from app.services.reconciliation_service import ReconciliationService


class FakeSub:
    def __init__(self, status=SubscriptionStatus.ACTIVE):
        self.id = uuid4()
        self.status = status
        self.stripe_subscription_id = "sub_123"


class FakeSubRepo:
    def __init__(self, subs):
        self.subs = subs

    def get_all_with_stripe_id(self):
        return self.subs


class FakeDb:
    def __init__(self):
        self.committed = False

    def commit(self):
        self.committed = True


class FakeStripe:
    def __init__(self, status="past_due", fail_times=0):
        self.status = status
        self.fail_times = fail_times
        self.calls = 0
        self.Subscription = SimpleNamespace(retrieve=self.retrieve)

    def retrieve(self, stripe_id):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ConnectionError("transient")
        return SimpleNamespace(status=self.status)


def make_service(stripe_client=None, subs=None, **kwargs):
    service = ReconciliationService(db=FakeDb(), stripe_client=stripe_client, **kwargs)
    service._sub_repo = FakeSubRepo(subs or [])
    return service


def test_reconciliation_skipped_without_stripe_client():
    service = make_service(stripe_client=None, subs=[FakeSub()])
    assert service.run_once() == 0


def test_reconciliation_syncs_status_change():
    sub = FakeSub()
    db = FakeDb()
    stripe_client = FakeStripe(status="past_due")
    service = make_service(stripe_client, [sub])
    service._db = db

    synced = service.run_once()

    assert synced == 1
    assert sub.status == SubscriptionStatus.PAST_DUE
    assert db.committed


def test_reconciliation_retries_transient_failure_then_succeeds():
    sub = FakeSub()
    stripe_client = FakeStripe(status="canceled", fail_times=2)
    service = make_service(stripe_client, [sub], attempts=3, base_delay=0)

    synced = service.run_once()

    assert synced == 1
    assert sub.status == SubscriptionStatus.CANCELLED


def test_reconciliation_no_change_when_already_synced():
    sub = FakeSub(status=SubscriptionStatus.PAST_DUE)
    stripe_client = FakeStripe(status="past_due")
    service = make_service(stripe_client, [sub])

    assert service.run_once() == 0
    assert sub.status == SubscriptionStatus.PAST_DUE
