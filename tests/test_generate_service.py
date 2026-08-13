"""Unit tests for the GenerateService wiring (Probe 1 + cost in response)."""

from types import SimpleNamespace
from uuid import uuid4

from app.constants.usage_type import UsageType
from app.schemas.usage import TokenUsageCreate
from app.services.generate_service import GenerateService


def make_event():
    return SimpleNamespace(
        id=uuid4(),
        subscription_id=uuid4(),
        usage_type=UsageType.TOKENS,
        quantity=4500,
        cached_input_tokens=2500,
        input_tokens=1000,
        output_tokens=500,
        reasoning_tokens=500,
    )


class FakeUsageService:
    def __init__(self, event):
        self.event = event
        self.calls = 0

    def record_usage(self, request):
        self.calls += 1
        return self.event


class FakeCostService:
    def calculate_token_cost(self, **kwargs):
        return 42

    def to_cents(self, micro_units):
        return round(micro_units / 10_000, 4)


def make_request():
    return TokenUsageCreate(
        subscription_id=uuid4(),
        cached_input_tokens=2500,
        input_tokens=1000,
        output_tokens=500,
        reasoning_tokens=500,
        idempotency_key="key-gen-1",
    )


def make_service(event):
    service = GenerateService(db=None)
    service.usage_service = FakeUsageService(event)
    service.cost_service = FakeCostService()
    return service


def test_generate_returns_event_and_cost():
    service = make_service(make_event())
    request = make_request()

    result = service.generate(request)

    assert result["usage_event"].quantity == 4500
    assert result["cost_micro"] == 42
    assert result["cost_cents"] == 0.0042
    assert service.usage_service.calls == 1


def test_generate_retry_returns_mirror_response():
    service = make_service(make_event())
    request = make_request()

    first = service.generate(request)
    second = service.generate(request)

    assert first == second
    assert service.usage_service.calls == 2
