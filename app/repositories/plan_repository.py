from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.schemas.plan import PlanCreate


class PlanRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, plan: PlanCreate):
        db_plan = Plan(**plan.model_dump())

        self.db.add(db_plan)
        self.db.commit()
        self.db.refresh(db_plan)

        return db_plan

    def get_all(self):
        return self.db.query(Plan).all()

    def get_by_id(self, plan_id):
        return self.db.query(Plan).filter(Plan.id == plan_id).first()

    def get_by_name(self, name: str):
        return self.db.query(Plan).filter(Plan.name == name).first()

    def get_by_stripe_price_id(self, stripe_price_id: str):
        return (
            self.db.query(Plan).filter(Plan.stripe_price_id == stripe_price_id).first()
        )
