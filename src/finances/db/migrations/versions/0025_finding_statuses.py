"""Create finding_statuses: findings a person handled (that month) or ignored (every month)."""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finding_statuses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("month", sa.Date(), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("set_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_finding_statuses"),
    )


def downgrade() -> None:
    op.drop_table("finding_statuses")
