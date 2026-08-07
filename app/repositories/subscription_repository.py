from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.schemas.subscription import SubscriptionCreate


class SubscriptionRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, subscription: SubscriptionCreate):

        db_subscription = Subscription(
            **subscription.model_dump()
        )

        self.db.add(db_subscription)
        self.db.commit()
        self.db.refresh(db_subscription)

        return db_subscription

    def get_all(self):
        return self.db.query(Subscription).all()

    def get_by_id(self, subscription_id):
        return (
            self.db.query(Subscription)
            .filter(
                Subscription.id == subscription_id
            )
            .first()
    )