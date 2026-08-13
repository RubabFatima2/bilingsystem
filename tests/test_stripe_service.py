"""Unit tests for the Stripe checkout + webhook handler (Probes 3 & 4).

Covers: forged signature -> 400 with nothing written, replay dedupe,
checkout.session.completed flipping a tenant Free -> Pro, and
customer.subscription.deleted cancelling the subscription.
"""
from types import SimpleNamespace
from uuid import uuid4

import pytest
import stripe
from fastapi import HTTPException

from app.constants.subscription_status import SubscriptionStatus
from app.models.webhook_event import WebhookEvent
from app.services.stripe_service import StripeService


class FakePlan:
    def __init__(self, name="Pro", stripe_price_id="price_pro"):
        self.id = uuid4()
        self.name = name
        self.stripe_price_id = stripe_price_id


class FakeSubscription:
    def __init__(
        self,
        tenant_id,
        plan_id,
        status=SubscriptionStatus.ACTIVE,
        stripe_subscription_id=None,
        stripe_customer_id=None,
    ):
        self.id = uuid4()
        self.tenant_id = tenant_id
        self.plan_id = plan_id
        self.status = status
        self.stripe_subscription_id = stripe_subscription_id
        self.stripe_customer_id = stripe_customer_id


class FakeSubRepo:
    def __init__(self, by_tenant=None, by_stripe=None):
        self.by_tenant = by_tenant or {}
        self.by_stripe = by_stripe or {}

    def get_by_tenant(self, tenant_id):
        return self.by_tenant.get(tenant_id)

    def get_by_stripe_subscription_id(self, stripe_subscription_id):
        return self.by_stripe.get(stripe_subscription_id)


class FakePlanRepo:
    def __init__(self, by_price=None):
        self.by_price = by_price or {}
        self.plans = {}

    def get_by_id(self, plan_id):
        return self.plans.get(plan_id)

    def get_by_stripe_price_id(self, price_id):
        return self.by_price.get(price_id)


class FakeWebhookRepo:
    def __init__(self):
        self.event_ids = set()

    def get_by_event_id(self, event_id):
        return event_id in self.event_ids


class FakeDb:
    def __init__(self, webhook_repo):
        self.webhook_repo = webhook_repo
        self.added = []
        self.committed = False
        self.rolled_back = False

    def add(self, obj):
        if isinstance(obj, WebhookEvent):
            self.webhook_repo.event_ids.add(obj.event_id)
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FakeStripe:
    """Drop-in fake for the injected Stripe client."""

    class SignatureVerificationError(stripe.error.SignatureVerificationError):
        def __init__(self, message=""):
            pass

    def __init__(self, event=None, raises=False):
        self.event = event
        self.raises = raises
        self.created_session = None
        self.Webhook = SimpleNamespace(
            construct_event=self._construct_event
        )
        self.checkout = SimpleNamespace(
            Session=SimpleNamespace(create=self._create_session)
        )

    def _construct_event(self, payload, sig_header, secret):
        if self.raises:
            raise FakeStripe.SignatureVerificationError("bad signature")
        return self.event

    def _create_session(self, **params):
        self.created_session = params
        return SimpleNamespace(url="https://checkout.stripe.com/c/pay/test")


def make_service(
    sub_repo,
    plan_repo,
    webhook_repo,
    stripe_client,
    secret="whsec_test",
):
    db = FakeDb(webhook_repo)
    service = StripeService(
        db=db,
        stripe_client=stripe_client,
        webhook_secret=secret,
    )
    service._sub_repo = sub_repo
    service._plan_repo = plan_repo
    service._webhook_repo = webhook_repo
    return service


def checkout_event(tenant_id, plan_id, customer="cus_123", stripe_sub="sub_123"):
    return {
        "id": "evt_checkout",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {
                    "tenant_id": str(tenant_id),
                    "plan_id": str(plan_id),
                },
                "customer": customer,
                "subscription": stripe_sub,
            }
        },
    }


def test_webhook_forged_signature_raises_400():
    tenant_id = uuid4()
    sub = FakeSubscription(tenant_id, uuid4())
    service = make_service(
        FakeSubRepo(by_tenant={tenant_id: sub}),
        FakePlanRepo(),
        FakeWebhookRepo(),
        FakeStripe(None, raises=True),
    )

    with pytest.raises(HTTPException) as exc_info:
        service.handle_webhook(b"payload", "t=1;v1=fake")

    assert exc_info.value.status_code == 400
    assert sub.status == SubscriptionStatus.ACTIVE
    assert service._webhook_repo.event_ids == set()


def test_webhook_missing_secret_raises_500():
    tenant_id = uuid4()
    service = make_service(
        FakeSubRepo(),
        FakePlanRepo(),
        FakeWebhookRepo(),
        FakeStripe(checkout_event(tenant_id, uuid4())),
        secret=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.handle_webhook(b"{}", "t=1;v1=x")

    assert exc_info.value.status_code == 500


def test_checkout_session_completed_flips_tenant_to_pro():
    tenant_id = uuid4()
    pro_plan_id = uuid4()
    sub = FakeSubscription(tenant_id, uuid4())
    webhook_repo = FakeWebhookRepo()
    service = make_service(
        FakeSubRepo(by_tenant={tenant_id: sub}),
        FakePlanRepo(),
        webhook_repo,
        FakeStripe(checkout_event(tenant_id, pro_plan_id)),
    )

    service.handle_webhook(b"payload", "t=1;v1=good")

    assert sub.plan_id == pro_plan_id
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.stripe_customer_id == "cus_123"
    assert sub.stripe_subscription_id == "sub_123"
    assert "evt_checkout" in webhook_repo.event_ids
    assert service._db.committed


def test_webhook_replay_is_ignored():
    tenant_id = uuid4()
    sub = FakeSubscription(tenant_id, uuid4())
    webhook_repo = FakeWebhookRepo()
    service = make_service(
        FakeSubRepo(by_tenant={tenant_id: sub}),
        FakePlanRepo(),
        webhook_repo,
        FakeStripe(checkout_event(tenant_id, uuid4())),
    )

    service.handle_webhook(b"payload", "t=1;v1=good")
    first_plan = sub.plan_id
    service.handle_webhook(b"payload", "t=1;v1=good")

    assert sub.plan_id == first_plan
    assert webhook_repo.event_ids == {"evt_checkout"}


def test_subscription_deleted_cancels_subscription():
    tenant_id = uuid4()
    sub = FakeSubscription(tenant_id, uuid4(), stripe_subscription_id="sub_123")
    event = {
        "id": "evt_deleted",
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "sub_123"}},
    }
    service = make_service(
        FakeSubRepo(by_stripe={"sub_123": sub}),
        FakePlanRepo(),
        FakeWebhookRepo(),
        FakeStripe(event),
    )

    service.handle_webhook(b"payload", "t=1;v1=good")

    assert sub.status == SubscriptionStatus.CANCELLED


def test_subscription_updated_syncs_status_and_plan():
    tenant_id = uuid4()
    pro_plan = FakePlan(stripe_price_id="price_pro")
    sub = FakeSubscription(tenant_id, uuid4(), stripe_subscription_id="sub_123")
    event = {
        "id": "evt_updated",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_123",
                "status": "active",
                "items": {"data": [{"price": {"id": "price_pro"}}]},
            }
        },
    }
    service = make_service(
        FakeSubRepo(by_stripe={"sub_123": sub}),
        FakePlanRepo(by_price={"price_pro": pro_plan}),
        FakeWebhookRepo(),
        FakeStripe(event),
    )

    service.handle_webhook(b"payload", "t=1;v1=good")

    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.plan_id == pro_plan.id


def test_create_checkout_session_returns_url(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "STRIPE_API_KEY", "sk_test_x")

    tenant_id = uuid4()
    pro_plan = FakePlan()
    plan_repo = FakePlanRepo()
    plan_repo.plans[pro_plan.id] = pro_plan
    stripe_client = FakeStripe()
    db = FakeDb(FakeWebhookRepo())
    service = StripeService(
        db=db,
        stripe_client=stripe_client,
        webhook_secret="whsec_test",
    )
    service._sub_repo = FakeSubRepo()
    service._plan_repo = plan_repo
    service._webhook_repo = FakeWebhookRepo()

    url = service.create_checkout_session(tenant_id, pro_plan.id)

    assert url == "https://checkout.stripe.com/c/pay/test"
    session_params = stripe_client.created_session
    assert session_params["mode"] == "subscription"
    assert session_params["line_items"][0]["price"] == "price_pro"
    assert session_params["metadata"]["tenant_id"] == str(tenant_id)
    assert session_params["metadata"]["plan_id"] == str(pro_plan.id)


def test_create_checkout_session_requires_stripe_price():
    tenant_id = uuid4()
    plan = FakePlan(stripe_price_id=None)
    plan_repo = FakePlanRepo()
    plan_repo.plans[plan.id] = plan
    service = StripeService(
        db=FakeDb(FakeWebhookRepo()),
        stripe_client=FakeStripe(),
        webhook_secret="whsec_test",
    )
    service._plan_repo = plan_repo

    with pytest.raises(HTTPException) as exc_info:
        service.create_checkout_session(tenant_id, plan.id)

    assert exc_info.value.status_code == 500
