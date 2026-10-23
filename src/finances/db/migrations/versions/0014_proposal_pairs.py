"""Add proposals.other_id: the inflow of a proposed transfer (or of one said not to be)."""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("proposals", sa.Column("other_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        batch.drop_column("other_id")
