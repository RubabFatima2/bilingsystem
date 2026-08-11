# from sqlalchemy.orm import Session

# from app.models.usage_event import UsageEvent
# from app.schemas.usage import UsageCreate
# from sqlalchemy import func

# class UsageRepository:

#     def __init__(self, db: Session):
#         self.db = db

#     def create(self, usage: UsageCreate):

#         event = UsageEvent(
#             **usage.model_dump()
#         )

#         self.db.add(event)
#         self.db.commit()
#         self.db.refresh(event)

#         return event

#     def get_all(self):
#         return self.db.query(UsageEvent).all()

#     def get_total_usage(self, subscription_id):
#         total = (
#             self.db.query(func.sum(UsageEvent.quantity))
#             .filter(
#                 UsageEvent.subscription_id == subscription_id
#             )
#             .scalar()
#     )
#         return total or 0

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.usage_event import UsageEvent
from app.schemas.usage import UsageCreate


class UsageRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_idempotency_key(self, idempotency_key: str):
        return (
            self.db.query(UsageEvent)
            .filter(
                UsageEvent.idempotency_key == idempotency_key
            )
            .first()
        )

    def create(self, usage: UsageCreate):
        existing = (
        self.db.query(UsageEvent)
        .filter(
            UsageEvent.idempotency_key
            == usage.idempotency_key
        )
        .first()
    )
        if existing:
          return existing

        event = UsageEvent(
        subscription_id=usage.subscription_id,
        quantity=usage.quantity,
        idempotency_key=usage.idempotency_key,
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