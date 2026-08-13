from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.tenant import (
    get_current_tenant_id,
    get_owned_subscription,
)
from app.schemas.usage import (
    UsageCreate,
    UsageResponse,
    UsageRollupResponse,
)
from app.services.cost_service import CostService
from app.services.usage_service import UsageService
from app.utils.dates import month_bounds

router = APIRouter(
    prefix="/usage",
    tags=["Usage"],
)


@router.post("", response_model=UsageResponse)
def record_usage(
    usage: UsageCreate,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    get_owned_subscription(usage.subscription_id, tenant_id, db)
    service = UsageService(db)
    return service.record_usage(usage)


@router.get("", response_model=list[UsageResponse])
def list_usage(
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    service = UsageService(db)
    return service.list_usage_for_tenant(tenant_id)


@router.get("/{subscription_id}", response_model=UsageRollupResponse)
def usage_rollup(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    get_owned_subscription(subscription_id, tenant_id, db)
    period_start, period_end = month_bounds()
    return CostService(db).rollup(subscription_id, period_start, period_end)
