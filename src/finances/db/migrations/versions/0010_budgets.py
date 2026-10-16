"""Create budgets: a monthly target for a category or a group."""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_budgets"),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], name="fk_budgets_category_id_categories"
        ),
        sa.UniqueConstraint("category_id", name="uq_budgets_category_id"),
    )


def downgrade() -> None:
    op.drop_table("budgets")
