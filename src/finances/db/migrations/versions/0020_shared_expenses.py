"""Create shared_expenses (who owes the payer for a transaction) and settlements."""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shared_expenses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("payer_id", sa.Integer(), nullable=False),
        sa.Column("debtor_id", sa.Integer(), nullable=False),
        sa.Column("owed_cents", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name="fk_shared_expenses_transaction_id_transactions",
        ),
        sa.ForeignKeyConstraint(
            ["payer_id"], ["people.id"], name="fk_shared_expenses_payer_id_people"
        ),
        sa.ForeignKeyConstraint(
            ["debtor_id"], ["people.id"], name="fk_shared_expenses_debtor_id_people"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_shared_expenses"),
        sa.UniqueConstraint("transaction_id", name="uq_shared_expenses_transaction_id"),
    )
    op.create_table(
        "settlements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payer_id", sa.Integer(), nullable=False),
        sa.Column("payee_id", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["payer_id"], ["people.id"], name="fk_settlements_payer_id_people"),
        sa.ForeignKeyConstraint(["payee_id"], ["people.id"], name="fk_settlements_payee_id_people"),
        sa.PrimaryKeyConstraint("id", name="pk_settlements"),
    )


def downgrade() -> None:
    op.drop_table("settlements")
    op.drop_table("shared_expenses")
