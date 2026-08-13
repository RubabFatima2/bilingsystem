from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.tenant import TenantCreate, TenantResponse
from app.services.tenant_service import TenantService

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.post("", response_model=TenantResponse)
def create_tenant(
    tenant: TenantCreate,
    db: Session = Depends(get_db),
):
    service = TenantService(db)
    return service.create_tenant(tenant)


@router.get("", response_model=list[TenantResponse])
def list_tenants(
    db: Session = Depends(get_db),
):
    service = TenantService(db)
    return service.list_tenants()
