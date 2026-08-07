from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SubscriptionCreate(BaseModel):
    tenant_id: UUID
    plan_id: UUID


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    plan_id: UUID
    status: str