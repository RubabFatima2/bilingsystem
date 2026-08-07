from sqlalchemy.orm import Session

from app.models.usage_event import UsageEvent
from app.schemas.usage import UsageCreate
from sqlalchemy import func

class UsageRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, usage: UsageCreate):

        event = UsageEvent(
            **usage.model_dump()
        )

        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        return event

    def get_all(self):
        return self.db.query(UsageEvent).all()




def get_total_usage(self, subscription_id):

    total = (
        self.db.query(func.sum(UsageEvent.quantity))
        .filter(
            UsageEvent.subscription_id == subscription_id
        )
        .scalar()
    )

    return total or 0