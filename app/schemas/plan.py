from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PlanCreate(BaseModel):
    name: str
    price: int
    usage_limit: int
    api_call_limit: int = 0
    tokens_limit: int = 0
    stripe_price_id: str | None = None
    stripe_product_id: str | None = None


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    price: int
    usage_limit: int
    api_call_limit: int
    tokens_limit: int
    stripe_price_id: str | None
    stripe_product_id: str | None
    is_active: bool
