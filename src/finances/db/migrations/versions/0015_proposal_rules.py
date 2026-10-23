"""Add proposals.pattern, match, and priority: the rule a rule proposal would add."""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        batch.add_column(sa.Column("pattern", sa.String(100), nullable=True))
        batch.add_column(sa.Column("match", sa.String(12), nullable=True))
        batch.add_column(sa.Column("priority", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        batch.drop_column("priority")
        batch.drop_column("match")
        batch.drop_column("pattern")
