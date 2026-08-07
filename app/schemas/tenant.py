from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class TenantCreate(BaseModel):
    name: str
    email: EmailStr


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: EmailStr
    is_active: bool