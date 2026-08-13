"""Real Stripe client construction for the request path and background jobs.

Injected clients keep the services unit-testable; this is the only place
that touches the Stripe SDK's global api_key.
"""

import stripe
from fastapi import HTTPException

from app.core.config import settings


def get_stripe_client(required: bool = False):
    """Return the Stripe module configured with the test-mode key.

    Returns ``None`` (or raises 500 when ``required``) if the key is unset,
    so the app and tests keep working without a Stripe account.
    """
    if not settings.STRIPE_API_KEY:
        if required:
            raise HTTPException(
                status_code=500,
                detail="STRIPE_API_KEY is not configured",
            )
        return None

    stripe.api_key = settings.STRIPE_API_KEY
    return stripe
