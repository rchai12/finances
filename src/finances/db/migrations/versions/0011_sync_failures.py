"""Create sync_failures: the last failed sync of each SimpleFIN link, cleared by a good one."""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_failures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("link", sa.String(30), nullable=False),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.String(200), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_sync_failures"),
        sa.UniqueConstraint("link", name="uq_sync_failures_link"),
    )


def downgrade() -> None:
    op.drop_table("sync_failures")
