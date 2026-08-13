"""Seed demo data: Free + Pro plans, a demo tenant and an active subscription.

Idempotent: re-running does not duplicate rows. Prints the ids you need for
the demo -- the tenant id doubles as the ``X-Tenant-Id`` header value.

Run from the repo root:  uv run python scripts/seed.py
"""
import sys
from pathlib import Path

# Allow running as `python scripts/seed.py` from anywhere in the repo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.constants.subscription_status import SubscriptionStatus  # noqa: E402
from app.core.logging import logger  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import Plan, Subscription, Tenant  # noqa: E402

# Money is integer cents. Monthly limits follow the capstone brief:
# Free 1,000 calls / 100k tokens, Pro higher.
PLAN_SPECS = [
    {
        "name": "Free",
        "price": 0,
        "usage_limit": 1_000,
        "api_call_limit": 1_000,
        "tokens_limit": 100_000,
    },
    {
        "name": "Pro",
        "price": 5_000,
        "usage_limit": 10_000,
        "api_call_limit": 10_000,
        "tokens_limit": 5_000_000,
    },
]


def main() -> None:
    db = SessionLocal()
    try:
        plans = {}
        for spec in PLAN_SPECS:
            plan = db.query(Plan).filter(Plan.name == spec["name"]).first()
            if plan is None:
                plan = Plan(**spec)
                db.add(plan)
                db.flush()
                logger.info("Created plan %s", spec["name"])
            else:
                logger.info("Plan %s already exists", spec["name"])
            plans[spec["name"]] = plan

        tenant = (
            db.query(Tenant)
            .filter(Tenant.email == "demo@example.com")
            .first()
        )
        if tenant is None:
            tenant = Tenant(name="Demo Tenant", email="demo@example.com")
            db.add(tenant)
            db.flush()
            logger.info("Created demo tenant")

        subscription = (
            db.query(Subscription)
            .filter(Subscription.tenant_id == tenant.id)
            .first()
        )
        if subscription is None:
            subscription = Subscription(
                tenant_id=tenant.id,
                plan_id=plans["Free"].id,
                status=SubscriptionStatus.ACTIVE,
            )
            db.add(subscription)
            logger.info("Created demo subscription")

        db.commit()

        print(f"Tenant id:       {tenant.id}")
        print(f"Free plan id:    {plans['Free'].id}")
        print(f"Pro plan id:     {plans['Pro'].id}")
        print(f"Subscription id: {subscription.id}")
        print("Use the tenant id as the X-Tenant-Id header value.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
