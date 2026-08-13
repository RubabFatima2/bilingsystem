import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.usage_type import UsageType
from app.db.base import Base


class UsageEvent(Base):
    __tablename__ = "usage_events"

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

    usage_type: Mapped[UsageType] = mapped_column(
        Enum(UsageType),
        default=UsageType.API_CALL,
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Token breakdown for TOKENS events so cost is always recomputable from
    # metered data (pricing rules live in the cost engine, not in stored
    # money). Nullable/default 0 for API_CALL events.
    cached_input_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    input_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    output_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    reasoning_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    idempotency_key: Mapped[str] = mapped_column(
    String,
    unique=True,
    nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    subscription = relationship(
        "Subscription",
        back_populates="usage_events",
    )