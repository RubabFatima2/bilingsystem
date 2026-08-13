"""Stripe checkout + webhook handling (test mode).

Responsibilities:

  * ``create_checkout_session`` builds a Stripe Checkout session (test mode)
    that creates a subscription, returning the hosted URL.
  * ``handle_webhook`` verifies the Stripe signature, deduplicates events by
    ``event.id`` (persisted in ``webhook_events`` so replays are no-ops even
    across restarts), and syncs the tenant's plan/status.

The Stripe client is injected so unit tests use a fake; the real client is
``app.integrations.stripe.get_stripe_client``.
"""
from uuid import UUID

import stripe
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.constants.subscription_status import (
    SubscriptionStatus,
    from_stripe_status,
)
from app.core.config import settings
from app.models.subscription import Subscription
from app.models.webhook_event import WebhookEvent
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.webhook_event_repository import WebhookEventRepository


class StripeService:

    def __init__(
        self,
        db: Session,
        stripe_client=None,
        webhook_secret: str | None = None,
    ):
        self._db = db
        self._stripe = stripe_client if stripe_client is not None else stripe
        self._webhook_secret = webhook_secret or settings.STRIPE_WEBHOOK_SECRET
        self._sub_repo = SubscriptionRepository(db)
        self._plan_repo = PlanRepository(db)
        self._webhook_repo = WebhookEventRepository(db)

    # -- checkout ---------------------------------------------------------

    def create_checkout_session(self, tenant_id: UUID, plan_id: UUID) -> str:
        """Create a Stripe Checkout session and return its hosted URL."""
        if not settings.STRIPE_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="STRIPE_API_KEY is not configured",
            )

        plan = self._plan_repo.get_by_id(plan_id)
        if plan is None:
            raise HTTPException(status_code=404, detail="Plan not found")
        if not plan.stripe_price_id:
            raise HTTPException(
                status_code=500,
                detail=f"Plan '{plan.name}' has no Stripe price id. "
                f"Create a test-mode price and set plan.stripe_price_id.",
            )

        existing = self._sub_repo.get_by_tenant(tenant_id)

        session_params = {
            "mode": "subscription",
            "line_items": [{"price": plan.stripe_price_id, "quantity": 1}],
            "success_url": settings.STRIPE_SUCCESS_URL,
            "cancel_url": settings.STRIPE_CANCEL_URL,
            "client_reference_id": str(tenant_id),
            "metadata": {
                "tenant_id": str(tenant_id),
                "plan_id": str(plan_id),
            },
        }
        if existing is not None and existing.stripe_customer_id:
            session_params["customer"] = existing.stripe_customer_id

        checkout_session = self._stripe.checkout.Session.create(
            **session_params
        )

        return checkout_session.url

    # -- webhook ----------------------------------------------------------

    def handle_webhook(self, payload: bytes, sig_header: str) -> None:
        """Verify signature, dedupe by event id, sync plan/status.

        A forged signature raises 400. A replayed event id is a no-op.
        The webhook marker row is committed atomically with the subscription
        changes, so a failure rolls back and Stripe's retry reprocesses.
        """
        if not self._webhook_secret:
            raise HTTPException(
                status_code=500,
                detail="STRIPE_WEBHOOK_SECRET is not configured",
            )

        try:
            event = self._stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=self._webhook_secret,
            )
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid signature")

        event_id = event["id"]
        if self._webhook_repo.get_by_event_id(event_id):
            return

        self._db.add(
            WebhookEvent(event_id=event_id, event_type=event["type"])
        )

        try:
            self._process_event(event)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

    def _process_event(self, event) -> None:
        event_type = event["type"]
        data = event["data"]["object"]

        if event_type == "checkout.session.completed":
            self._sync_from_checkout(data)
        elif event_type == "customer.subscription.updated":
            self._sync_subscription_status(data)
        elif event_type == "customer.subscription.deleted":
            self._cancel_subscription(data)

    def _sync_from_checkout(self, session_obj) -> None:
        metadata = session_obj.get("metadata") or {}
        tenant_id = UUID(metadata["tenant_id"])
        plan_id = UUID(metadata["plan_id"])

        subscription = self._sub_repo.get_by_tenant(tenant_id)
        if subscription is None:
            subscription = Subscription(
                tenant_id=tenant_id,
                plan_id=plan_id,
                status=SubscriptionStatus.ACTIVE,
            )
            self._db.add(subscription)

        subscription.plan_id = plan_id
        subscription.status = SubscriptionStatus.ACTIVE
        if session_obj.get("customer"):
            subscription.stripe_customer_id = session_obj["customer"]
        if session_obj.get("subscription"):
            subscription.stripe_subscription_id = session_obj["subscription"]

    def _sync_subscription_status(self, sub_obj) -> None:
        stripe_sub_id = sub_obj.get("id")
        if not stripe_sub_id:
            return

        subscription = self._sub_repo.get_by_stripe_subscription_id(
            stripe_sub_id
        )
        if subscription is None:
            return

        subscription.status = from_stripe_status(sub_obj.get("status"))

        price_id = _price_id_from_items(sub_obj)
        if price_id:
            plan = self._plan_repo.get_by_stripe_price_id(price_id)
            if plan is not None:
                subscription.plan_id = plan.id

    def _cancel_subscription(self, sub_obj) -> None:
        stripe_sub_id = sub_obj.get("id")
        if not stripe_sub_id:
            return

        subscription = self._sub_repo.get_by_stripe_subscription_id(
            stripe_sub_id
        )
        if subscription is None:
            return

        subscription.status = SubscriptionStatus.CANCELLED


def _price_id_from_items(sub_obj) -> str | None:
    try:
        return sub_obj["items"]["data"][0]["price"]["id"]
    except (KeyError, IndexError, TypeError):
        return None
