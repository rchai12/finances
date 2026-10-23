"""Create proposals (the agent's suggestions, waiting for a person) and advice_log (its notes)."""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proposals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_proposals"),
    )
    op.create_table(
        "advice_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("text", sa.String(1000), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_advice_log"),
    )


def downgrade() -> None:
    op.drop_table("advice_log")
    op.drop_table("proposals")
