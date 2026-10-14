"""Create categories (seeded with a default two-level tree), category_rules, and
transaction_categories."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# Each group, its kind ("" when none), and its categories, in the order they are inserted.
DEFAULT_TREE = (
    ("Food", "", ("Groceries", "Dining", "Coffee & Dessert")),
    ("Home", "", ("Rent & Mortgage", "Utilities & Internet", "Home & Garden")),
    (
        "Transport",
        "",
        ("Gas", "Parking & Tolls", "Public Transit", "Rideshare & Taxi", "Car Maintenance"),
    ),
    ("Shopping", "", ("General Shopping", "Clothing", "Electronics")),
    ("Subscriptions", "", ("Subscriptions & Digital",)),
    ("Health", "sensitive", ("Medical", "Pharmacy", "Fitness")),
    ("Personal", "", ("Personal Care", "Gifts & Donations", "Education")),
    ("Travel", "", ("Flights", "Lodging", "Travel Other")),
    ("Entertainment", "", ("Entertainment & Events", "Gaming")),
    ("Financial", "", ("Fees & Interest", "Insurance", "Taxes")),
    ("Transfers", "transfer", ("Transfer", "Credit Card Payment")),
    ("Income", "income", ("Paycheck", "Interest Income", "Other Income")),
)


def upgrade() -> None:
    categories = op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("is_transfer", sa.Boolean(), nullable=False),
        sa.Column("is_income", sa.Boolean(), nullable=False),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["categories.id"], name="fk_categories_parent_id_categories"
        ),
        sa.UniqueConstraint("name", name="uq_categories_name"),
    )
    op.create_table(
        "category_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pattern", sa.String(100), nullable=False),
        sa.Column("match", sa.String(12), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_category_rules"),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], name="fk_category_rules_category_id_categories"
        ),
        sa.UniqueConstraint("match", "pattern", name="uq_category_rules_match_pattern"),
    )
    op.create_table(
        "transaction_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_transaction_categories"),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name="fk_transaction_categories_transaction_id_transactions",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_transaction_categories_category_id_categories",
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["category_rules.id"],
            name="fk_transaction_categories_rule_id_category_rules",
        ),
        sa.UniqueConstraint("transaction_id", name="uq_transaction_categories_transaction_id"),
    )
    rows = []
    next_id = len(DEFAULT_TREE) + 1
    for group_id, (group, kind, children) in enumerate(DEFAULT_TREE, start=1):
        flags = {
            "is_transfer": kind == "transfer",
            "is_income": kind == "income",
            "is_sensitive": kind == "sensitive",
        }
        rows.append({"id": group_id, "name": group, "parent_id": None, **flags})
        for child in children:
            rows.append({"id": next_id, "name": child, "parent_id": group_id, **flags})
            next_id += 1
    op.bulk_insert(categories, rows)


def downgrade() -> None:
    op.drop_table("transaction_categories")
    op.drop_table("category_rules")
    op.drop_table("categories")
