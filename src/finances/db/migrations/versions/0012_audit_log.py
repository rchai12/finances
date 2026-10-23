"""Create audit_log: one row per change a person made to the household's data, never edited."""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("who", sa.String(10), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=True),
        sa.Column("before", sa.String(200), nullable=True),
        sa.Column("after", sa.String(200), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
