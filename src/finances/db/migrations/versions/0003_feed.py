"""Create the feed_items and feed_pulls tables."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feed_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("feed_id", sa.String(100), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_feed_items"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="fk_feed_items_account_id_accounts"
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name="fk_feed_items_transaction_id_transactions",
        ),
        sa.UniqueConstraint("account_id", "feed_id", name="uq_feed_items_account_feed"),
        sa.UniqueConstraint("transaction_id", name="uq_feed_items_transaction_id"),
    )
    op.create_table(
        "feed_pulls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("inserted", sa.Integer(), nullable=False),
        sa.Column("updated", sa.Integer(), nullable=False),
        sa.Column("removed", sa.Integer(), nullable=False),
        sa.Column("unchanged", sa.Integer(), nullable=False),
        sa.Column("feed_total_cents", sa.BigInteger(), nullable=False),
        sa.Column("balance_cents", sa.BigInteger(), nullable=True),
        sa.Column("balance_date", sa.Date(), nullable=True),
        sa.Column("drift_cents", sa.BigInteger(), nullable=True),
        sa.Column("pulled_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_feed_pulls"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="fk_feed_pulls_account_id_accounts"
        ),
    )
    op.create_index("ix_feed_pulls_account_id", "feed_pulls", ["account_id"], unique=False)


def downgrade() -> None:
    op.drop_table("feed_items")
    op.drop_table("feed_pulls")
