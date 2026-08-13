"""Billable-endpoint orchestration: meter an AI response.

POST /generate is the capstone's one dummy billable endpoint. It:

  1. meters a token usage event (exactly-once by idempotency key)
  2. enforces the plan's tokens quota (429 if exceeded, 402 if not active)
  3. computes the cost of the response from the metered token categories

The cost rules (cached-input cheaper, reasoning-as-output) live in the
CostService; this service just wires metering + quota + cost together.
"""

from app.schemas.usage import TokenUsageCreate, UsageResponse
from app.services.cost_service import CostService
from app.services.usage_service import UsageService


class GenerateService:
    def __init__(self, db):
        self.usage_service = UsageService(db)
        self.cost_service = CostService(db)

    def generate(self, request: TokenUsageCreate) -> dict:
        """Meter one AI response and return the event plus its cost.

        A retry with the same idempotency key is deduplicated by
        UsageService.record_usage (Probe 1) and returns the original event;
        the cost is recomputed from the event's stored token breakdown so a
        retry returns a mirror response.
        """
        event = self.usage_service.record_usage(request)

        cost_micro = self.cost_service.calculate_token_cost(
            cached_input_tokens=event.cached_input_tokens,
            input_tokens=event.input_tokens,
            output_tokens=event.output_tokens,
            reasoning_tokens=event.reasoning_tokens,
        )

        return {
            "usage_event": UsageResponse.model_validate(event),
            "cost_micro": cost_micro,
            "cost_cents": self.cost_service.to_cents(cost_micro),
        }
