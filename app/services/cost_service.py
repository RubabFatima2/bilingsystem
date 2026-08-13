import math

from app.constants.pricing import CENTS_TO_MICRO, PRICING
from app.constants.usage_type import UsageType
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.usage_repository import UsageRepository


def _per_1k_micro(cents_per_1k: float) -> int:
    """Convert a float 'cents per 1k' rate into integer micro-units/1k.

    Micro-units = cents x 10,000. The conversion is exact for the two-decimal
    rates pinned in PRICING, so money math never touches floats.
    """
    return round(cents_per_1k * CENTS_TO_MICRO)


# Precompute integer micro-unit-per-1k rates once at import time.
RATES = {key: _per_1k_micro(value) for key, value in PRICING.items()}


class CostService:
    """Converts metered usage into money, using pinned integer pricing.

    Money is always returned in micro-units (int); callers that need cents
    divide by CENTS_TO_MICRO. No floats in the money path.
    """

    def __init__(self, db):
        self._db = db
        self.RATES = RATES
        self._subscription_repo = SubscriptionRepository(db)
        self._usage_repo = UsageRepository(db)

    def calculate_token_cost(
        self,
        cached_input_tokens: int,
        input_tokens: int,
        output_tokens: int,
        reasoning_tokens: int,
    ) -> int:
        """Cost in micro-units of one AI response.

        Rules encoded (brief section 3):
          * reasoning tokens are billed as output tokens -> added to the
            output bucket before pricing
          * cached input is priced at its own (cheaper) rate
          * each category is priced separately per 1k block, then summed --
            they are never added together as raw token counts

        Per-1k blocks round UP (ceil) so a partial block pays the full block
        rate -- exact at block boundaries.
        """
        output_total = output_tokens + reasoning_tokens

        cached = math.ceil(cached_input_tokens / 1000) * RATES["cached_input_per_1k"]
        fresh = math.ceil(input_tokens / 1000) * RATES["input_per_1k"]
        output = math.ceil(output_total / 1000) * RATES["output_per_1k"]

        return cached + fresh + output

    def calculate_api_call_cost(self, quantity: int) -> int:
        """Cost in micro-units of `quantity` api-call events."""
        return math.ceil(quantity / 1000) * RATES["api_call_per_1k"]

    def to_cents(self, micro_units: int) -> float:
        return round(micro_units / CENTS_TO_MICRO, 4)

    def rollup(self, subscription_id, period_start, period_end):
        """Per-subscription usage rollup for a billing period.

        Returns used/limit/cost per usage type, matching the brief's
        GET /usage contract: { used, limit, cost }.
        """
        subscription = self._subscription_repo.get_by_id(subscription_id)
        if subscription is None:
            return None

        plan = subscription.plan

        used_api_calls = self._usage_repo.get_total_by_type(
            subscription_id, UsageType.API_CALL, period_start, period_end
        )
        used_tokens = self._usage_repo.get_total_by_type(
            subscription_id, UsageType.TOKENS, period_start, period_end
        )

        cached, fresh, output, reasoning = self._usage_repo.get_token_totals(
            subscription_id, period_start, period_end
        )

        api_cost = self.calculate_api_call_cost(used_api_calls)
        token_cost = self.calculate_token_cost(
            cached_input_tokens=cached,
            input_tokens=fresh,
            output_tokens=output,
            reasoning_tokens=reasoning,
        )
        total_cost = api_cost + token_cost

        return {
            "subscription_id": subscription_id,
            "plan_id": plan.id,
            "used_api_calls": used_api_calls,
            "api_call_limit": plan.api_call_limit,
            "used_tokens": used_tokens,
            "tokens_limit": plan.tokens_limit,
            "cost_micro": total_cost,
            "cost_cents": self.to_cents(total_cost),
        }
