"""Create the statements, transactions, and balance_snapshots tables."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "statements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("source_filename", sa.String(255), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("parser_name", sa.String(50), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("opening_balance_cents", sa.BigInteger(), nullable=False),
        sa.Column("closing_balance_cents", sa.BigInteger(), nullable=False),
        sa.Column("lines_parsed", sa.Integer(), nullable=False),
        sa.Column("rows_inserted", sa.Integer(), nullable=False),
        sa.Column("rows_duplicate", sa.Integer(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_statements"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="fk_statements_account_id_accounts"
        ),
        sa.UniqueConstraint("file_sha256", name="uq_statements_file_sha256"),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=True),
        sa.Column("posted_date", sa.Date(), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=True),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("section", sa.String(30), nullable=True),
        sa.Column("card_last4", sa.String(4), nullable=True),
        sa.Column("cardholder", sa.String(100), nullable=True),
        sa.Column("external_id", sa.String(100), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("is_pending", sa.Boolean(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_transactions"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="fk_transactions_account_id_accounts"
        ),
        sa.ForeignKeyConstraint(
            ["statement_id"], ["statements.id"], name="fk_transactions_statement_id_statements"
        ),
        sa.UniqueConstraint(
            "account_id", "fingerprint", name="uq_transactions_account_fingerprint"
        ),
    )
    op.create_index("ix_transactions_account_id", "transactions", ["account_id"], unique=False)
    op.create_index("ix_transactions_posted_date", "transactions", ["posted_date"], unique=False)
    op.create_table(
        "balance_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("balance_cents", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_balance_snapshots"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="fk_balance_snapshots_account_id_accounts"
        ),
        sa.UniqueConstraint(
            "account_id",
            "as_of_date",
            "source",
            name="uq_balance_snapshots_account_date_source",
        ),
    )


def downgrade() -> None:
    op.drop_table("transactions")
    op.drop_table("balance_snapshots")
    op.drop_table("statements")
