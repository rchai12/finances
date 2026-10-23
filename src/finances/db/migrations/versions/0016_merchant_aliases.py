"""Create merchant_aliases: a cleaned merchant name merged into another."""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merchant_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("target", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_merchant_aliases"),
        sa.UniqueConstraint("source", name="uq_merchant_aliases_source"),
    )


def downgrade() -> None:
    op.drop_table("merchant_aliases")
