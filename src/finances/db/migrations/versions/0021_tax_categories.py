"""Add categories.is_tax, and mark the seeded Medical, Gifts & Donations, and Taxes."""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

TAX = ("Medical", "Gifts & Donations", "Taxes")


def upgrade() -> None:
    op.add_column(
        "categories", sa.Column("is_tax", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    categories = sa.table(
        "categories",
        sa.column("name", sa.String()),
        sa.column("parent_id", sa.Integer()),
        sa.column("is_tax", sa.Boolean()),
    )
    op.execute(
        categories.update()
        .where(categories.c.name.in_(TAX), categories.c.parent_id.is_not(None))
        .values(is_tax=True)
    )


def downgrade() -> None:
    op.drop_column("categories", "is_tax")
