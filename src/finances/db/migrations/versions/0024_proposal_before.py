"""Add proposals.before: what a proposal changes, as it was when the agent proposed it."""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        batch.add_column(sa.Column("before", sa.String(200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        batch.drop_column("before")
