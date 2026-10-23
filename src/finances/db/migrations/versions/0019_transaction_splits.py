"""Create transaction_splits: the parts of a transaction, each with its own category."""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transaction_splits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name="fk_transaction_splits_transaction_id_transactions",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_transaction_splits_category_id_categories",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transaction_splits"),
        sa.UniqueConstraint(
            "transaction_id", "position", name="uq_transaction_splits_transaction_id_position"
        ),
    )


def downgrade() -> None:
    op.drop_table("transaction_splits")
