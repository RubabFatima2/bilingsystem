"""Unit tests for BillingService (overage + per-period invoice dedupe)."""
from uuid import uuid4

from app.services.billing_service import BillingService


class FakePlan:
    price = 1000
    usage_limit = 1000


class FakeSubscription:
    def __init__(self):
        self.id = uuid4()
        self.plan = FakePlan()


class FakeSubRepo:
    def __init__(self, subscription):
        self.subscription = subscription

    def get_by_id(self, subscription_id):
        self.subscription.id = subscription_id
        return self.subscription


class FakeUsageRepo:
    def get_total_usage(self, subscription_id, start, end):
        return 1200


class FakeInvoice:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeInvoiceRepo:
    def __init__(self):
        self.created = []
        self.existing = None

    def get_by_subscription_and_period(self, subscription_id, start, end):
        return self.existing

    def create(self, invoice):
        self.created.append(invoice)
        return invoice


def make_service(invoice_repo):
    service = BillingService(db=None)
    service.subscription_repo = FakeSubRepo(FakeSubscription())
    service.usage_repo = FakeUsageRepo()
    service.invoice_repo = invoice_repo
    return service


def test_calculate_bill_charges_plan_plus_overage():
    invoice_repo = FakeInvoiceRepo()
    service = make_service(invoice_repo)
    subscription_id = uuid4()

    result = service.calculate_bill(subscription_id)

    assert result["plan_price"] == 1000
    assert result["total_usage"] == 1200
    assert result["usage_limit"] == 1000
    assert result["overage"] == 200
    assert result["amount_due"] == 1000 + 200 * BillingService.OVERAGE_PRICE

    invoice = invoice_repo.created[0]
    assert invoice.subscription_id == subscription_id
    assert invoice.period_start is not None
    assert invoice.period_end is not None


def test_calculate_bill_does_not_duplicate_invoice_for_period():
    invoice_repo = FakeInvoiceRepo()
    service = make_service(invoice_repo)
    subscription_id = uuid4()

    first = service.calculate_bill(subscription_id)
    existing = invoice_repo.created[0]
    invoice_repo.existing = existing
    second = service.calculate_bill(subscription_id)

    assert second["amount_due"] == first["amount_due"]
    assert len(invoice_repo.created) == 1


def test_calculate_bill_no_overage_below_limit():
    invoice_repo = FakeInvoiceRepo()

    class LowUsageRepo:
        def get_total_usage(self, subscription_id, start, end):
            return 500

    service = make_service(invoice_repo)
    service.usage_repo = LowUsageRepo()

    result = service.calculate_bill(uuid4())

    assert result["overage"] == 0
    assert result["amount_due"] == 1000
