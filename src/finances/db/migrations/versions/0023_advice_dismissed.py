"""Add advice_log.dismissed_at: when a person dismissed one of the agent's notes."""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("advice_log") as batch:
        batch.add_column(sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("advice_log") as batch:
        batch.drop_column("dismissed_at")
