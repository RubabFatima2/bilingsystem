from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.plan import PlanCreate, PlanResponse
from app.services.plan_service import PlanService

router = APIRouter(
    prefix="/plans",
    tags=["Plans"],
)


@router.post("", response_model=PlanResponse)
def create_plan(
    plan: PlanCreate,
    db: Session = Depends(get_db),
):
    service = PlanService(db)
    return service.create_plan(plan)


@router.get("", response_model=list[PlanResponse])
def list_plans(
    db: Session = Depends(get_db),
):
    service = PlanService(db)
    return service.list_plans()