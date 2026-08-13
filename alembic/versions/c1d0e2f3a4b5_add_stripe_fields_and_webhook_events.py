"""add stripe fields and webhook_events

Revision ID: c1d0e2f3a4b5
Revises: 2a29408dbf7d
Create Date: 2026-08-12 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d0e2f3a4b5"
down_revision: str | Sequence[str] | None = "2a29408dbf7d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )

    op.add_column(
        "subscriptions",
        sa.Column("stripe_customer_id", sa.String(), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("stripe_subscription_id", sa.String(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_subscriptions_stripe_subscription_id",
        "subscriptions",
        ["stripe_subscription_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_subscriptions_stripe_subscription_id",
        "subscriptions",
        type_="unique",
    )
    op.drop_column("subscriptions", "stripe_subscription_id")
    op.drop_column("subscriptions", "stripe_customer_id")
    op.drop_table("webhook_events")
