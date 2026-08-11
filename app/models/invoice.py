import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id"),
        nullable=False,
    )

    plan_price: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    usage_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    total_usage: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    overage: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    amount_due: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    subscription = relationship("Subscription")