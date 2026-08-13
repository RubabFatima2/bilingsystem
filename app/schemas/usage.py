from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.constants.usage_type import UsageType


class UsageCreate(BaseModel):
    subscription_id: UUID
    quantity: int = Field(gt=0)
    usage_type: UsageType = UsageType.API_CALL
    idempotency_key: str


class TokenUsageCreate(UsageCreate):
    """A billable AI response: one metered token event with cost math inputs.

    usage_type is pinned to TOKENS so a caller cannot record token usage
    under the api_call type by mistake. quantity is derived from the token
    categories (total tokens) rather than taken from the caller.
    """

    usage_type: UsageType = UsageType.TOKENS
    quantity: int = 0  # overridden by the validator below
    cached_input_tokens: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    reasoning_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def _derive_quantity(self):
        self.quantity = (
            self.cached_input_tokens
            + self.input_tokens
            + self.output_tokens
            + self.reasoning_tokens
        )
        return self


class UsageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subscription_id: UUID
    usage_type: UsageType
    quantity: int


class UsageRollupResponse(BaseModel):
    subscription_id: UUID
    plan_id: UUID
    used_api_calls: int
    api_call_limit: int
    used_tokens: int
    tokens_limit: int
    cost_micro: int
    cost_cents: float
