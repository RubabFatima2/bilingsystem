from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate


class TenantRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, tenant: TenantCreate) -> Tenant:
        db_tenant = Tenant(
            name=tenant.name,
            email=tenant.email,
        )

        self.db.add(db_tenant)
        self.db.commit()
        self.db.refresh(db_tenant)

        return db_tenant

    def get_by_email(self, email: str):
        return self.db.query(Tenant).filter(Tenant.email == email).first()

    def get_by_id(self, tenant_id):
        return self.db.query(Tenant).filter(Tenant.id == tenant_id).first()

    def get_all(self):
        return self.db.query(Tenant).all()
