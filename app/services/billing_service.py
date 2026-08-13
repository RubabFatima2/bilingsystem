"""Monthly billing calculation with overage (a stretch goal).

One invoice per subscription per billing period; the period defaults to the
current calendar month. Money is integer cents throughout (the brief's rule:
store money as integers, never floats).
"""
from datetime import datetime

from app.core.exceptions import ResourceNotFoundException
from app.models.invoice import Invoice
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.usage_repository import UsageRepository
from app.utils.dates import month_bounds


class BillingService:

    # Cents charged per unit of usage over the plan's usage_limit.
    OVERAGE_PRICE = 10

    def __init__(self, db):
        self.subscription_repo = SubscriptionRepository(db)
        self.usage_repo = UsageRepository(db)
        self.invoice_repo = InvoiceRepository(db)

    def calculate_bill(
        self,
        subscription_id,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ):
        subscription = self.subscription_repo.get_by_id(subscription_id)
        if subscription is None:
            raise ResourceNotFoundException(
                f"Subscription {subscription_id} not found"
            )

        plan = subscription.plan

        start, end = period_start, period_end
        if start is None or end is None:
            start, end = month_bounds()

        total_usage = self.usage_repo.get_total_usage(
            subscription_id, start, end
        )

        overage = max(total_usage - plan.usage_limit, 0)
        amount_due = plan.price + overage * self.OVERAGE_PRICE

        # One invoice per subscription per period: a repeat calculation for
        # the same period returns the stored invoice instead of duplicating.
        existing_invoice = self.invoice_repo.get_by_subscription_and_period(
            subscription_id, start, end
        )
        if existing_invoice:
            return self._to_dict(existing_invoice)

        invoice = Invoice(
            subscription_id=subscription.id,
            plan_price=plan.price,
            usage_limit=plan.usage_limit,
            total_usage=total_usage,
            overage=overage,
            amount_due=amount_due,
            period_start=start,
            period_end=end,
        )

        self.invoice_repo.create(invoice)

        return self._to_dict(invoice)

    @staticmethod
    def _to_dict(invoice):
        return {
            "subscription_id": invoice.subscription_id,
            "plan_price": invoice.plan_price,
            "usage_limit": invoice.usage_limit,
            "total_usage": invoice.total_usage,
            "overage": invoice.overage,
            "amount_due": invoice.amount_due,
        }
