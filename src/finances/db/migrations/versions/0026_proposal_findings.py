"""Add the finding a proposal names: its type, subject, and month (finding_status proposals)."""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        batch.add_column(sa.Column("finding_type", sa.String(30), nullable=True))
        batch.add_column(sa.Column("finding_subject", sa.String(100), nullable=True))
        batch.add_column(sa.Column("finding_month", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        batch.drop_column("finding_month")
        batch.drop_column("finding_subject")
        batch.drop_column("finding_type")
