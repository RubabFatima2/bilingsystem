from sqlalchemy.orm import Session

from app.models.invoice import Invoice


class InvoiceRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, invoice: Invoice):
        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)

        return invoice
    def get_all(self):
        return self.db.query(Invoice).all()


    def get_by_subscription_id(self, subscription_id):
      return (
        self.db.query(Invoice)
        .filter(Invoice.subscription_id == subscription_id)
        .order_by(Invoice.created_at.desc())
        .first()
    )