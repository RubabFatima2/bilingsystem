from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subscription_id: UUID
    plan_price: int
    usage_limit: int
    total_usage: int
    overage: int
    amount_due: int
    created_at: datetime
