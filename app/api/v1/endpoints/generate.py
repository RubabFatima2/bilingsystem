from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.tenant import (
    get_current_tenant_id,
    get_owned_subscription,
)
from app.schemas.usage import TokenUsageCreate
from app.services.generate_service import GenerateService

router = APIRouter(tags=["Generate"])


@router.post("/generate")
def generate(
    request: TokenUsageCreate,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    get_owned_subscription(request.subscription_id, tenant_id, db)
    return GenerateService(db).generate(request)
