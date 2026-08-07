from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.usage import UsageCreate, UsageResponse
from app.services.usage_service import UsageService

router = APIRouter(
    prefix="/usage",
    tags=["Usage"],
)


@router.post("", response_model=UsageResponse)
def record_usage(
    usage: UsageCreate,
    db: Session = Depends(get_db),
):
    service = UsageService(db)
    return service.record_usage(usage)


@router.get("", response_model=list[UsageResponse])
def list_usage(
    db: Session = Depends(get_db),
):
    service = UsageService(db)
    return service.list_usage()