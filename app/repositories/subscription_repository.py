from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.schemas.subscription import SubscriptionCreate


class SubscriptionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, subscription: SubscriptionCreate):

        db_subscription = Subscription(**subscription.model_dump())

        self.db.add(db_subscription)
        self.db.commit()
        self.db.refresh(db_subscription)

        return db_subscription

    def get_all(self):
        return self.db.query(Subscription).all()

    def get_by_id(self, subscription_id):
        return (
            self.db.query(Subscription)
            .filter(Subscription.id == subscription_id)
            .first()
        )

    def get_by_tenant(self, tenant_id):
        return (
            self.db.query(Subscription)
            .filter(Subscription.tenant_id == tenant_id)
            .first()
        )

    def get_by_stripe_subscription_id(self, stripe_subscription_id: str):
        return (
            self.db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == stripe_subscription_id)
            .first()
        )

    def get_all_with_stripe_id(self):
        return (
            self.db.query(Subscription)
            .filter(Subscription.stripe_subscription_id.isnot(None))
            .all()
        )
