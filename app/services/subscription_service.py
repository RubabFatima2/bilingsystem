from app.repositories.subscription_repository import (
    SubscriptionRepository,
)


class SubscriptionService:

    def __init__(self, db):
        self.repository = SubscriptionRepository(db)

    def create_subscription(self, subscription):
        return self.repository.create(subscription)

    def list_subscriptions(self):
        return self.repository.get_all()