from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.invoice import InvoiceResponse
from app.services.invoice_service import InvoiceService

router = APIRouter()


@router.get("", response_model=list[InvoiceResponse])
def list_invoices(db: Session = Depends(get_db)):
    service = InvoiceService(db)
    return service.list_invoices()