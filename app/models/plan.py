import uuid

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    price: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    usage_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Per-usage-type limits. api_call_limit covers POST /generate style
    # billable actions; tokens_limit covers AI-token usage. usage_limit is
    # kept as the legacy total; api_call_limit is backfilled from it by the
    # migration that introduces these columns.
    api_call_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    tokens_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Stripe test-mode identifiers used to keep plans in sync with Stripe.
    stripe_price_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    stripe_product_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    subscriptions = relationship(
        "Subscription",
        back_populates="plan",
    )
