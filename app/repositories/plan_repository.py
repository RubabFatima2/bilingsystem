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

    def get_by_name(self, name: str):
        return (
            self.db.query(Plan)
            .filter(Plan.name == name)
            .first()
        )