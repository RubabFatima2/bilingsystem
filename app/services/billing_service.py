from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import (
    SubscriptionRepository,
)
from app.repositories.usage_repository import UsageRepository


class BillingService:

    OVERAGE_PRICE = 10

    def __init__(self, db):

        self.subscription_repo = SubscriptionRepository(db)
        self.usage_repo = UsageRepository(db)

    def calculate_bill(self, subscription_id):

        subscription = self.subscription_repo.get_by_id(
            subscription_id
        )

        plan = subscription.plan

        total_usage = self.usage_repo.get_total_usage(
            subscription_id
        )

        overage = max(
            total_usage - plan.usage_limit,
            0,
        )

        amount_due = (
            plan.price +
            overage * self.OVERAGE_PRICE
        )

        return {
            "subscription_id": subscription.id,
            "plan_price": plan.price,
            "usage_limit": plan.usage_limit,
            "total_usage": total_usage,
            "overage": overage,
            "amount_due": amount_due,
        }