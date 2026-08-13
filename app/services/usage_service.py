from app.constants.subscription_status import SubscriptionStatus
from app.constants.usage_type import UsageType
from app.core.exceptions import (
    QuotaExceededException,
    ResourceNotFoundException,
    SubscriptionNotActiveException,
)
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.usage_repository import UsageRepository
from app.utils.dates import month_bounds


class UsageService:

    def __init__(self, db):
        self.repository = UsageRepository(db)
        self.subscription_repo = SubscriptionRepository(db)

    def record_usage(self, usage):

        # Idempotency short-circuit: a retried request with the same
        # idempotency key returns the original event -- no new row, no quota
        # re-check, no double count. This is the exactly-once guarantee.
        existing = self.repository.get_by_idempotency_key(
            usage.idempotency_key
        )
        if existing is not None:
            return existing

        subscription = self.subscription_repo.get_by_id(
            usage.subscription_id
        )

        if subscription is None:
            raise ResourceNotFoundException(
                f"Subscription {usage.subscription_id} not found"
            )

        if subscription.status != SubscriptionStatus.ACTIVE:
            raise SubscriptionNotActiveException(
                f"Subscription {usage.subscription_id} is "
                f"{subscription.status.value}; an active plan is required "
                f"to record usage. Upgrade or renew to continue."
            )

        usage_type = usage.usage_type
        period_start, period_end = month_bounds()
        current_usage = self.repository.get_total_by_type(
            usage.subscription_id,
            usage_type,
            period_start,
            period_end,
        )

        limit = (
            subscription.plan.api_call_limit
            if usage_type == UsageType.API_CALL
            else subscription.plan.tokens_limit
        )

        # Boundary rule: at exactly the limit (current + requested == limit)
        # the request is allowed; only *exceeding* the limit is rejected.
        if current_usage + usage.quantity > limit:
            raise QuotaExceededException(
                f"Usage quota exceeded. "
                f"Limit: {limit}, "
                f"Current: {current_usage}, "
                f"Requested: {usage.quantity}"
            )

        return self.repository.create(usage)

    def list_usage(self):
        return self.repository.get_all()

    def list_usage_for_tenant(self, tenant_id):
        return self.repository.get_all_by_tenant(tenant_id)
