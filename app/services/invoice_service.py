from app.repositories.invoice_repository import InvoiceRepository


class InvoiceService:

    def __init__(self, db):
        self.repository = InvoiceRepository(db)

    def list_invoices(self):
        return self.repository.get_all()