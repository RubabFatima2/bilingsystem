from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.tenant import (
    get_current_tenant_id,
    get_owned_subscription,
)
from app.schemas.billing import BillingResponse
from app.services.billing_service import BillingService

router = APIRouter(
    prefix="/billing",
    tags=["Billing"],
)


@router.get(
    "/{subscription_id}",
    response_model=BillingResponse,
)
def calculate_bill(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    get_owned_subscription(subscription_id, tenant_id, db)
    service = BillingService(db)
    return service.calculate_bill(
        subscription_id
    )
