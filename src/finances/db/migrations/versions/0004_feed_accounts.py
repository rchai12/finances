"""Create the feed_accounts table."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feed_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("provider_account_id", sa.String(200), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_feed_accounts"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="fk_feed_accounts_account_id_accounts"
        ),
        sa.UniqueConstraint("account_id", name="uq_feed_accounts_account_id"),
        sa.UniqueConstraint("provider_account_id", name="uq_feed_accounts_provider_account_id"),
    )


def downgrade() -> None:
    op.drop_table("feed_accounts")
