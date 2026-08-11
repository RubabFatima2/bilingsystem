from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UsageCreate(BaseModel):
    subscription_id: UUID
    quantity: int = Field(gt=0)
    idempotency_key: str


class UsageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subscription_id: UUID
    quantity: int