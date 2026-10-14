"""Create the people, account_owners, and cardholder_aliases tables."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "people",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_people"),
        sa.UniqueConstraint("name", name="uq_people_name"),
    )
    op.create_table(
        "account_owners",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_account_owners"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="fk_account_owners_account_id_accounts"
        ),
        sa.ForeignKeyConstraint(
            ["person_id"], ["people.id"], name="fk_account_owners_person_id_people"
        ),
        sa.UniqueConstraint("account_id", name="uq_account_owners_account_id"),
    )
    op.create_table(
        "cardholder_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cardholder", sa.String(100), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_cardholder_aliases"),
        sa.ForeignKeyConstraint(
            ["person_id"], ["people.id"], name="fk_cardholder_aliases_person_id_people"
        ),
        sa.UniqueConstraint("cardholder", name="uq_cardholder_aliases_cardholder"),
    )


def downgrade() -> None:
    op.drop_table("cardholder_aliases")
    op.drop_table("account_owners")
    op.drop_table("people")
