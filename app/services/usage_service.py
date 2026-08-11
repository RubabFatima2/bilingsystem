from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.usage_repository import UsageRepository


class UsageService:

    def __init__(self, db):
        self.repository = UsageRepository(db)
        self.subscription_repo = SubscriptionRepository(db)

    def record_usage(self, usage):

        subscription = self.subscription_repo.get_by_id(
            usage.subscription_id
        )

        current_usage = self.repository.get_total_usage(
            usage.subscription_id
        )

        usage_limit = subscription.plan.usage_limit

        if current_usage + usage.quantity > usage_limit:
            raise ValueError(
                f"Usage limit exceeded. "
                f"Limit: {usage_limit}, "
                f"Current: {current_usage}, "
                f"Requested: {usage.quantity}"
            )

        return self.repository.create(usage)

    def list_usage(self):
        return self.repository.get_all()