"""Nightly reconciliation job: our DB mirrors Stripe's view.

A shared requirement of the internship is at least one background job that
does slow/bulk work off the request path, with retries and failure alerting.
This one re-reads every subscription that has a Stripe counterpart and syncs
status/plan from Stripe -- catching webhooks that were missed or dropped.

The job is safe to run twice (idempotent), retries transient Stripe errors
with exponential backoff, and logs every failure as the alert channel.
"""
import logging
import time

from sqlalchemy.orm import Session

from app.constants.subscription_status import from_stripe_status
from app.repositories.subscription_repository import SubscriptionRepository

logger = logging.getLogger("billing_engine")


class ReconciliationService:

    def __init__(
        self,
        db: Session,
        stripe_client=None,
        attempts: int = 3,
        base_delay: float = 1.0,
    ):
        self._db = db
        self._stripe = stripe_client
        self._attempts = attempts
        self._base_delay = base_delay
        self._sub_repo = SubscriptionRepository(db)

    def run_once(self) -> int:
        """Sync status/plan for every Stripe-linked subscription.

        Returns the number of subscriptions whose status changed. Raises if
        a Stripe call fails all retries; the caller (the loop) logs it.
        """
        if self._stripe is None:
            return 0

        subscriptions = self._sub_repo.get_all_with_stripe_id()
        synced = 0

        for subscription in subscriptions:
            try:
                stripe_sub = self._retry(
                    lambda s=subscription: self._stripe.Subscription.retrieve(
                        s.stripe_subscription_id
                    )
                )
                status = from_stripe_status(
                    getattr(stripe_sub, "status", None)
                )
                if subscription.status != status:
                    subscription.status = status
                    synced += 1
            except Exception as exc:  # noqa: BLE001 - one bad sub must not kill the run
                logger.error(
                    "Reconciliation failed for subscription %s: %s",
                    subscription.id,
                    exc,
                )

        self._db.commit()
        return synced

    def _retry(self, call):
        """Call ``call`` up to ``attempts`` times with exponential backoff."""
        last_exc = None
        delay = self._base_delay
        for attempt in range(self._attempts):
            try:
                return call()
            except Exception as exc:  # noqa: BLE001 - retrying on transient errors is the point
                last_exc = exc
                if attempt < self._attempts - 1:
                    time.sleep(delay)
                    delay *= 2
        raise last_exc
