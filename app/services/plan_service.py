from fastapi import HTTPException

from app.repositories.plan_repository import PlanRepository


class PlanService:
    def __init__(self, db):
        self.repository = PlanRepository(db)

    def create_plan(self, plan):

        if self.repository.get_by_name(plan.name):
            raise HTTPException(
                status_code=400,
                detail="Plan already exists",
            )

        return self.repository.create(plan)

    def list_plans(self):
        return self.repository.get_all()
