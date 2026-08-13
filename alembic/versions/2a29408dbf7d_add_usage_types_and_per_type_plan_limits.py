"""add usage types and per-type plan limits

Revision ID: 2a29408dbf7d
Revises: 4c4dce7abd0f
Create Date: 2026-08-11 16:25:08.685784

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2a29408dbf7d'
down_revision: str | Sequence[str] | None = '4c4dce7abd0f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    usage_type = sa.Enum(
        "API_CALL",
        "TOKENS",
        name="usagetype",
    )
    usage_type.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "usage_events",
        sa.Column(
            "usage_type",
            usage_type,
            nullable=True,
        ),
    )

    op.execute("UPDATE usage_events SET usage_type = 'API_CALL'")

    op.alter_column(
        "usage_events",
        "usage_type",
        nullable=False,
    )

    op.add_column(
        "plans",
        sa.Column("api_call_limit", sa.Integer(), nullable=True),
    )
    op.add_column(
        "plans",
        sa.Column("tokens_limit", sa.Integer(), nullable=True),
    )
    op.add_column(
        "plans",
        sa.Column("stripe_price_id", sa.String(), nullable=True),
    )
    op.add_column(
        "plans",
        sa.Column("stripe_product_id", sa.String(), nullable=True),
    )

    # Backfill: existing plans only metered api-call style usage, so their
    # api_call_limit is the historical usage_limit. tokens_limit defaults to
    # 0 for legacy rows; seeded/Pro plans set it explicitly.
    op.execute(
        "UPDATE plans "
        "SET api_call_limit = usage_limit, tokens_limit = 0"
    )

    op.alter_column("plans", "api_call_limit", nullable=False)
    op.alter_column("plans", "tokens_limit", nullable=False)

    # Token breakdown columns (used by the cost engine to recompute exact
    # cost from metered data; zero for API_CALL events).
    op.add_column(
        "usage_events",
        sa.Column("cached_input_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "usage_events",
        sa.Column("input_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "usage_events",
        sa.Column("output_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "usage_events",
        sa.Column("reasoning_tokens", sa.Integer(), nullable=True),
    )

    op.execute("UPDATE usage_events SET cached_input_tokens = 0, "
               "input_tokens = 0, output_tokens = 0, reasoning_tokens = 0")

    op.alter_column("usage_events", "cached_input_tokens", nullable=False)
    op.alter_column("usage_events", "input_tokens", nullable=False)
    op.alter_column("usage_events", "output_tokens", nullable=False)
    op.alter_column("usage_events", "reasoning_tokens", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("usage_events", "reasoning_tokens")
    op.drop_column("usage_events", "output_tokens")
    op.drop_column("usage_events", "input_tokens")
    op.drop_column("usage_events", "cached_input_tokens")
    op.drop_column("plans", "tokens_limit")
    op.drop_column("plans", "api_call_limit")
    op.drop_column("plans", "stripe_product_id")
    op.drop_column("plans", "stripe_price_id")
    op.drop_column("usage_events", "usage_type")

    sa.Enum(
        "API_CALL",
        "TOKENS",
        name="usagetype",
    ).drop(op.get_bind(), checkfirst=True)
