"""Unit tests for UsageService quota enforcement + idempotency.

These cover the "boundary honesty" requirement of the capstone brief:
a request at / under / over the limit, plus clean 4xx errors instead of a
500 for a missing or non-active subscription, and the exactly-once retry
guarantee (Probe 1).
"""
from uuid import uuid4

import pytest

from app.constants.subscription_status import SubscriptionStatus
from app.constants.usage_type import UsageType
from app.core.exceptions import (
    QuotaExceededException,
    ResourceNotFoundException,
    SubscriptionNotActiveException,
)
from app.schemas.usage import UsageCreate
from app.services.usage_service import UsageService


class FakePlan:
    api_call_limit = 1000
    tokens_limit = 100_000


class FakeSubscription:
    def __init__(self, status=SubscriptionStatus.ACTIVE):
        self.status = status
        self.plan = FakePlan()


class FakeSubscriptionRepo:
    def __init__(self, subscription):
        self.subscription = subscription

    def get_by_id(self, subscription_id):
        return self.subscription


# Sentinel so the helper can distinguish "no subscription passed" (build a
# fake active one) from "explicitly missing" (repo returns None -> 404).
_MISSING = object()


class FakeUsageRepo:
    def __init__(self, current_by_type=None, existing_key=None):
        self.current_by_type = current_by_type or {}
        self.created = []
        self.existing_key = existing_key

    def get_by_idempotency_key(self, key):
        return self.existing_key

    def get_total_by_type(self, subscription_id, usage_type, *args):
        return self.current_by_type.get(usage_type, 0)

    def create(self, usage):
        self.created.append(usage)
        return usage


def make_service(
    current_usage=0,
    subscription=_MISSING,
    status=SubscriptionStatus.ACTIVE,
):
    sub = (
        FakeSubscription(status=status)
        if subscription is _MISSING
        else subscription
    )
    service = UsageService(db=None)
    service.subscription_repo = FakeSubscriptionRepo(sub)
    # A plain int means "API_CALL usage of that amount"; a dict lets tests
    # set per-type usage explicitly.
    current_by_type = (
        current_usage
        if isinstance(current_usage, dict)
        else {UsageType.API_CALL: current_usage}
    )
    service.repository = FakeUsageRepo(current_by_type)
    return service


def make_usage(quantity, usage_type=UsageType.API_CALL, key="key-1"):
    return UsageCreate(
        subscription_id=uuid4(),
        quantity=quantity,
        usage_type=usage_type,
        idempotency_key=key,
    )


def test_missing_subscription_raises_404():
    service = make_service(subscription=None)

    with pytest.raises(ResourceNotFoundException):
        service.record_usage(make_usage(1))


def test_non_active_subscription_raises_402():
    service = make_service(status=SubscriptionStatus.CANCELLED)

    with pytest.raises(SubscriptionNotActiveException) as exc_info:
        service.record_usage(make_usage(1))
    assert exc_info.value.status_code == 402


def test_usage_under_limit_is_recorded():
    service = make_service(current_usage=500)

    result = service.record_usage(make_usage(1))

    assert len(service.repository.created) == 1
    assert result is service.repository.created[0]


def test_usage_exactly_at_limit_is_recorded():
    # Boundary rule: current + requested == limit is allowed (not rejected).
    service = make_service(current_usage=999)

    result = service.record_usage(make_usage(1))

    assert len(service.repository.created) == 1
    assert result is service.repository.created[0]


def test_usage_over_limit_raises_429():
    service = make_service(current_usage=1000)

    with pytest.raises(QuotaExceededException) as exc_info:
        service.record_usage(make_usage(1))

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == "3600"
    # No usage event may be recorded for a rejected request.
    assert len(service.repository.created) == 0


def test_usage_that_would_hit_limit_but_never_commits():
    # Ensure the repository create() is only called once and only when
    # allowed -- a rejected request must not write anything.
    service = make_service(current_usage=999)

    with pytest.raises(QuotaExceededException):
        service.record_usage(make_usage(2))

    assert len(service.repository.created) == 0


def test_token_usage_uses_tokens_limit():
    # Token usage is checked against tokens_limit, not api_call_limit.
    service = make_service(
        current_usage={UsageType.TOKENS: 99_999},
    )

    service.record_usage(
        make_usage(1, usage_type=UsageType.TOKENS),
    )

    assert len(service.repository.created) == 1


def test_token_usage_over_tokens_limit_raises_429():
    service = make_service(
        current_usage={UsageType.TOKENS: 100_000},
    )

    with pytest.raises(QuotaExceededException):
        service.record_usage(
            make_usage(1, usage_type=UsageType.TOKENS),
        )

    assert len(service.repository.created) == 0


def test_retry_with_same_key_returns_existing_without_recording():
    # Probe 1: the second request with the same idempotency key returns the
    # first event, records nothing new.
    existing = object()
    service = UsageService(db=None)
    service.subscription_repo = FakeSubscriptionRepo(FakeSubscription())
    service.repository = FakeUsageRepo(
        current_by_type={UsageType.API_CALL: 500},
        existing_key=existing,
    )

    result = service.record_usage(make_usage(1, key="key-dup"))

    assert result is existing
    assert len(service.repository.created) == 0
