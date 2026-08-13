import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.subscription_status import SubscriptionStatus
from app.db.base import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plans.id"),
        nullable=False,
    )

    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
    )

    # Stripe test-mode identifiers kept so verified webhooks and the nightly
    # reconciliation job can map Stripe objects back to this subscription.
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String,
        unique=True,
        nullable=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    tenant = relationship(
        "Tenant",
        back_populates="subscriptions",
    )

    plan = relationship(
        "Plan",
        back_populates="subscriptions",
    )
    usage_events = relationship(
        "UsageEvent",
        back_populates="subscription",
        cascade="all, delete-orphan",
    )
    invoices = relationship(
        "Invoice",
        back_populates="subscription",
        cascade="all, delete-orphan",
    )
