"""Unit tests for the CostService (AI-token pricing rules + rollup).

Probe 5: cached-input and reasoning-token rules must produce the exact
expected totals, and GET /usage must match.
"""
from uuid import uuid4

import pytest

from app.constants.pricing import CENTS_TO_MICRO
from app.constants.usage_type import UsageType
from app.services.cost_service import CostService


def make_service():
    return CostService(db=None)


# --- calculate_token_cost -------------------------------------------------

def test_reasoning_tokens_are_billed_as_output():
    """1000 reasoning tokens == 1000 output tokens at output rate."""
    svc = make_service()
    cost = svc.calculate_token_cost(
        cached_input_tokens=0,
        input_tokens=0,
        output_tokens=0,
        reasoning_tokens=1000,
    )
    output_rate = 6000  # 0.60 cents/1k -> 0.60 * 10_000 micro-units
    assert cost == output_rate


def test_cached_input_cheaper_than_fresh():
    """1000 cached input tokens cost less than 1000 fresh input tokens."""
    svc = make_service()
    cached = svc.calculate_token_cost(
        cached_input_tokens=1000, input_tokens=0, output_tokens=0, reasoning_tokens=0
    )
    fresh = svc.calculate_token_cost(
        cached_input_tokens=0, input_tokens=1000, output_tokens=0, reasoning_tokens=0
    )
    assert cached < fresh


def test_categories_are_not_added_as_raw_tokens():
    """Pricing is per-category, not on the summed raw count.

    1000 cached + 1000 fresh + 1000 output must equal the per-category sum,
    NOT what you'd get pricing the total 3000 at one rate.
    """
    svc = make_service()
    cost = svc.calculate_token_cost(
        cached_input_tokens=1000,
        input_tokens=1000,
        output_tokens=1000,
        reasoning_tokens=0,
    )
    expected = (
        (1000 // 1000) * svc.RATES["cached_input_per_1k"]
        + (1000 // 1000) * svc.RATES["input_per_1k"]
        + (1000 // 1000) * svc.RATES["output_per_1k"]
    )
    assert cost == expected


def test_partial_block_rounds_up_to_full_block():
    """1 token pays the same as 1000 tokens (ceil to block)."""
    svc = make_service()
    one = svc.calculate_token_cost(
        cached_input_tokens=0, input_tokens=1, output_tokens=0, reasoning_tokens=0
    )
    thousand = svc.calculate_token_cost(
        cached_input_tokens=0, input_tokens=1000, output_tokens=0, reasoning_tokens=0
    )
    assert one == thousand


def test_cached_plus_reasoning_mixed_total():
    """A realistic mixed response: cached input + fresh input + output +
    reasoning (billed as output)."""
    svc = make_service()
    cost = svc.calculate_token_cost(
        cached_input_tokens=2500,
        input_tokens=3000,
        output_tokens=4000,
        reasoning_tokens=500,
    )
    # 2500 cached -> ceil(2.5)=3 blocks * cached_rate
    # 3000 fresh  -> 3 blocks * fresh_rate
    # 4500 output (4000+500) -> 5 blocks * output_rate
    expected = (
        3 * svc.RATES["cached_input_per_1k"]
        + 3 * svc.RATES["input_per_1k"]
        + 5 * svc.RATES["output_per_1k"]
    )
    assert cost == expected


# --- calculate_api_call_cost ----------------------------------------------

def test_api_call_cost_rounds_blocks_up():
    svc = make_service()
    assert svc.calculate_api_call_cost(1000) == svc.RATES["api_call_per_1k"]
    assert svc.calculate_api_call_cost(1) == svc.RATES["api_call_per_1k"]


# --- to_cents -------------------------------------------------------------

def test_to_cents_converts_micro_units():
    svc = make_service()
    assert svc.to_cents(1000 * CENTS_TO_MICRO) == 1000.0
    assert svc.to_cents(CENTS_TO_MICRO) == 1.0


# --- rollup (Probe 5) ------------------------------------------------------

class FakePlan:
    id = uuid4()
    api_call_limit = 1000
    tokens_limit = 100_000


class FakeSubscription:
    plan = FakePlan()


class FakeSubscriptionRepo:
    def get_by_id(self, subscription_id):
        return FakeSubscription()


class FakeUsageRepo:
    def get_total_by_type(self, subscription_id, usage_type, *args):
        return {
            UsageType.API_CALL: 1000,
            UsageType.TOKENS: 10_000,
        }.get(usage_type, 0)

    def get_token_totals(self, subscription_id, *args):
        return (2000, 3000, 4000, 500)


class FakeCostService(CostService):
    def __init__(self):
        # skip the real __init__ (needs a db)
        self._subscription_repo = FakeSubscriptionRepo()
        self._usage_repo = FakeUsageRepo()


def test_rollup_returns_used_limit_cost():
    svc = FakeCostService()
    result = svc.rollup(uuid4(), None, None)

    assert result["used_api_calls"] == 1000
    assert result["api_call_limit"] == 1000
    assert result["used_tokens"] == 10_000
    assert result["tokens_limit"] == 100_000

    # cost = api_call cost + token cost recomputed from category sums
    expected_api = svc.calculate_api_call_cost(1000)
    expected_tokens = svc.calculate_token_cost(2000, 3000, 4000, 500)
    assert result["cost_micro"] == expected_api + expected_tokens
    assert result["cost_cents"] == svc.to_cents(expected_api + expected_tokens)


def test_rollup_missing_subscription_returns_none():
    class NoSubRepo:
        def get_by_id(self, subscription_id):
            return None

    svc = FakeCostService()
    svc._subscription_repo = NoSubRepo()
    assert svc.rollup(uuid4(), None, None) is None
