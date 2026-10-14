"""Create transfer_pairs (an outflow and an inflow that are one transfer) and transfer_rejections
(pairs the household said are not a transfer)."""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transfer_pairs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("out_transaction_id", sa.Integer(), nullable=False),
        sa.Column("in_transaction_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_transfer_pairs"),
        sa.ForeignKeyConstraint(
            ["out_transaction_id"],
            ["transactions.id"],
            name="fk_transfer_pairs_out_transaction_id_transactions",
        ),
        sa.ForeignKeyConstraint(
            ["in_transaction_id"],
            ["transactions.id"],
            name="fk_transfer_pairs_in_transaction_id_transactions",
        ),
        sa.UniqueConstraint("out_transaction_id", name="uq_transfer_pairs_out_transaction_id"),
        sa.UniqueConstraint("in_transaction_id", name="uq_transfer_pairs_in_transaction_id"),
    )
    op.create_table(
        "transfer_rejections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("out_transaction_id", sa.Integer(), nullable=False),
        sa.Column("in_transaction_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_transfer_rejections"),
        sa.ForeignKeyConstraint(
            ["out_transaction_id"],
            ["transactions.id"],
            name="fk_transfer_rejections_out_transaction_id_transactions",
        ),
        sa.ForeignKeyConstraint(
            ["in_transaction_id"],
            ["transactions.id"],
            name="fk_transfer_rejections_in_transaction_id_transactions",
        ),
        sa.UniqueConstraint(
            "out_transaction_id", "in_transaction_id", name="uq_transfer_rejections_pair"
        ),
    )


def downgrade() -> None:
    op.drop_table("transfer_rejections")
    op.drop_table("transfer_pairs")
