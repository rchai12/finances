"""Create the feed_seen_accounts table: every SimpleFIN account a sync has delivered."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feed_seen_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("link", sa.String(50), nullable=False),
        sa.Column("provider_account_id", sa.String(200), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("institution", sa.String(100), nullable=False),
        sa.Column("first_seen", sa.Date(), nullable=False),
        sa.Column("last_seen", sa.Date(), nullable=False),
        sa.Column("ignored", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_feed_seen_accounts"),
        sa.UniqueConstraint(
            "link", "provider_account_id", name="uq_feed_seen_accounts_link_provider_account"
        ),
    )


def downgrade() -> None:
    op.drop_table("feed_seen_accounts")
