"""Add to proposals what a proposed group or category needs, and the proposal one waits for."""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

ADDED = ("group_name", "is_transfer", "is_income", "is_sensitive", "is_tax", "parent_id")


def upgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        batch.add_column(sa.Column("group_name", sa.String(50), nullable=True))
        batch.add_column(sa.Column("is_transfer", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("is_income", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("is_sensitive", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("is_tax", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("parent_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        for name in reversed(ADDED):
            batch.drop_column(name)
