from app.repositories.invoice_repository import InvoiceRepository


class InvoiceService:
    def __init__(self, db):
        self.repository = InvoiceRepository(db)

    def list_invoices(self):
        return self.repository.get_all()

    def list_for_tenant(self, tenant_id):
        return self.repository.get_all_by_tenant(tenant_id)
