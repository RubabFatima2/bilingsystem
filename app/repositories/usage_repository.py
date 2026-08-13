from datetime import datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.constants.usage_type import UsageType
from app.models.subscription import Subscription
from app.models.usage_event import UsageEvent
from app.schemas.usage import UsageCreate


class UsageRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_idempotency_key(self, idempotency_key: str):
        return (
            self.db.query(UsageEvent)
            .filter(UsageEvent.idempotency_key == idempotency_key)
            .first()
        )

    def create(self, usage: UsageCreate):
        # The unique constraint on idempotency_key is the real guard against
        # double-counting. Under concurrent retries two requests can pass the
        # SELECT above and race the INSERT; the winner's row wins and the
        # loser re-reads the committed row instead of failing.
        try:
            event = UsageEvent(
                subscription_id=usage.subscription_id,
                usage_type=usage.usage_type,
                quantity=usage.quantity,
                cached_input_tokens=getattr(usage, "cached_input_tokens", 0),
                input_tokens=getattr(usage, "input_tokens", 0),
                output_tokens=getattr(usage, "output_tokens", 0),
                reasoning_tokens=getattr(usage, "reasoning_tokens", 0),
                idempotency_key=usage.idempotency_key,
            )

            self.db.add(event)
            self.db.commit()
            self.db.refresh(event)
            return event
        except IntegrityError:
            self.db.rollback()
            return self.get_by_idempotency_key(usage.idempotency_key)

    def get_all(self):
        return self.db.query(UsageEvent).all()

    def get_all_by_tenant(self, tenant_id):
        return (
            self.db.query(UsageEvent)
            .join(Subscription, Subscription.id == UsageEvent.subscription_id)
            .filter(Subscription.tenant_id == tenant_id)
            .order_by(UsageEvent.created_at.desc())
            .all()
        )

    def get_total_usage(
        self,
        subscription_id,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ):
        query = self.db.query(func.sum(UsageEvent.quantity)).filter(
            UsageEvent.subscription_id == subscription_id
        )

        if period_start is not None:
            query = query.filter(UsageEvent.created_at >= period_start)
        if period_end is not None:
            query = query.filter(UsageEvent.created_at < period_end)

        return query.scalar() or 0

    def get_total_by_type(
        self,
        subscription_id,
        usage_type: UsageType,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ):
        """Sum of quantity for one usage type, optionally within a period."""
        query = self.db.query(func.sum(UsageEvent.quantity)).filter(
            UsageEvent.subscription_id == subscription_id,
            UsageEvent.usage_type == usage_type,
        )

        if period_start is not None:
            query = query.filter(UsageEvent.created_at >= period_start)
        if period_end is not None:
            query = query.filter(UsageEvent.created_at < period_end)

        return query.scalar() or 0

    def get_token_totals(
        self,
        subscription_id,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ):
        """Per-category token sums for TOKENS events in the period."""
        query = self.db.query(
            func.coalesce(func.sum(UsageEvent.cached_input_tokens), 0),
            func.coalesce(func.sum(UsageEvent.input_tokens), 0),
            func.coalesce(func.sum(UsageEvent.output_tokens), 0),
            func.coalesce(func.sum(UsageEvent.reasoning_tokens), 0),
        ).filter(
            UsageEvent.subscription_id == subscription_id,
            UsageEvent.usage_type == UsageType.TOKENS,
        )

        if period_start is not None:
            query = query.filter(UsageEvent.created_at >= period_start)
        if period_end is not None:
            query = query.filter(UsageEvent.created_at < period_end)

        return query.one()
