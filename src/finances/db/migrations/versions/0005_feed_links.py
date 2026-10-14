"""Add feed_accounts.link, so one aggregator account id can be mapped once per link."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("feed_accounts") as batch:
        batch.add_column(sa.Column("link", sa.String(50), nullable=True))
    feed_accounts = sa.table("feed_accounts", sa.column("link", sa.String(50)))
    op.execute(sa.update(feed_accounts).values(link="default"))
    with op.batch_alter_table("feed_accounts") as batch:
        batch.alter_column("link", existing_type=sa.String(50), nullable=False)
        batch.drop_constraint("uq_feed_accounts_provider_account_id", type_="unique")
        batch.create_unique_constraint(
            "uq_feed_accounts_link_provider_account", ["link", "provider_account_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("feed_accounts") as batch:
        batch.drop_constraint("uq_feed_accounts_link_provider_account", type_="unique")
        batch.drop_column("link")
        batch.create_unique_constraint(
            "uq_feed_accounts_provider_account_id", ["provider_account_id"]
        )
