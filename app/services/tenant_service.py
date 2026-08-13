from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.repositories.tenant_repository import TenantRepository
from app.schemas.tenant import TenantCreate


class TenantService:
    def __init__(self, db: Session):
        self.repository = TenantRepository(db)

    def create_tenant(self, tenant: TenantCreate):

        if self.repository.get_by_email(tenant.email):
            raise HTTPException(
                status_code=400,
                detail="Email already exists",
            )

        return self.repository.create(tenant)

    def list_tenants(self):
        return self.repository.get_all()
