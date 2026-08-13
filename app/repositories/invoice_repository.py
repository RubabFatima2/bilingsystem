from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.subscription import Subscription


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

    def get_all_by_tenant(self, tenant_id):
        return (
            self.db.query(Invoice)
            .join(Subscription, Subscription.id == Invoice.subscription_id)
            .filter(Subscription.tenant_id == tenant_id)
            .order_by(Invoice.created_at.desc())
            .all()
        )

    def get_by_subscription_id(self, subscription_id):
        return (
            self.db.query(Invoice)
            .filter(Invoice.subscription_id == subscription_id)
            .order_by(Invoice.created_at.desc())
            .first()
        )

    def get_by_subscription_and_period(
        self,
        subscription_id,
        period_start,
        period_end,
    ):
        return (
            self.db.query(Invoice)
            .filter(
                Invoice.subscription_id == subscription_id,
                Invoice.period_start == period_start,
                Invoice.period_end == period_end,
            )
            .first()
        )
