"""Create transaction_tags (many tags per transaction) and transaction_notes (one note each)."""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transaction_tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("tag", sa.String(30), nullable=False),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name="fk_transaction_tags_transaction_id_transactions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transaction_tags"),
        sa.UniqueConstraint("transaction_id", "tag", name="uq_transaction_tags_transaction_id_tag"),
    )
    op.create_table(
        "transaction_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(500), nullable=False),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name="fk_transaction_notes_transaction_id_transactions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transaction_notes"),
        sa.UniqueConstraint("transaction_id", name="uq_transaction_notes_transaction_id"),
    )


def downgrade() -> None:
    op.drop_table("transaction_notes")
    op.drop_table("transaction_tags")
