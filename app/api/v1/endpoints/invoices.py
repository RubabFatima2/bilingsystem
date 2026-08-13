from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.tenant import get_current_tenant_id
from app.schemas.invoice import InvoiceResponse
from app.services.invoice_service import InvoiceService

router = APIRouter()


@router.get("", response_model=list[InvoiceResponse])
def list_invoices(
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    service = InvoiceService(db)
    return service.list_for_tenant(tenant_id)
