"""Tenant authorization: every tenant-scoped request identifies itself.

``X-Tenant-Id`` is the tenant's identity (a UUID). Ownership checks reject
access to another tenant's subscription with 403 -- the multi-tenant
isolation guarantee from the capstone brief.
"""

from uuid import UUID

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundException
from app.models.subscription import Subscription
from app.repositories.subscription_repository import SubscriptionRepository


def get_current_tenant_id(
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
) -> UUID:
    try:
        return UUID(x_tenant_id)
    except ValueError, TypeError:
        raise HTTPException(
            status_code=400,
            detail="X-Tenant-Id header must be a valid UUID",
        )


def get_owned_subscription(
    subscription_id: UUID,
    tenant_id: UUID,
    db: Session,
) -> Subscription:
    """Return the subscription, or 404/403 if missing / not owned."""
    subscription = SubscriptionRepository(db).get_by_id(subscription_id)
    if subscription is None:
        raise ResourceNotFoundException(f"Subscription {subscription_id} not found")
    if subscription.tenant_id != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Subscription does not belong to this tenant",
        )
    return subscription
