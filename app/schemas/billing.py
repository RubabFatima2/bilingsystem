from uuid import UUID

from pydantic import BaseModel


class BillingResponse(BaseModel):
    subscription_id: UUID
    plan_price: int
    usage_limit: int
    total_usage: int
    overage: int
    amount_due: int