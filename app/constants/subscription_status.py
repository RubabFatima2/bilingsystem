from enum import Enum


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"


def from_stripe_status(stripe_status: str | None) -> SubscriptionStatus:
    """Translate a Stripe subscription status to our SubscriptionStatus."""
    if stripe_status == "trialing":
        return SubscriptionStatus.TRIALING
    if stripe_status in ("past_due", "unpaid"):
        return SubscriptionStatus.PAST_DUE
    if stripe_status in ("canceled", "incomplete_expired"):
        return SubscriptionStatus.CANCELLED
    return SubscriptionStatus.ACTIVE
