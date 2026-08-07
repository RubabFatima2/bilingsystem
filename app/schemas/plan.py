from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PlanCreate(BaseModel):
    name: str
    price: int
    usage_limit: int


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    price: int
    usage_limit: int
    is_active: bool