from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

import finances.db
from finances.db.engine import get_engine, session_scope
from finances.db.orm import Base, CategoryRow, CategoryRuleRow, TransactionCategoryRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
SOURCE = MIGRATIONS / "versions" / "0008_categories.py"
COLUMNS = {
    "categories": [
        ("id", "INTEGER", False),
        ("name", "VARCHAR(50)", False),
        ("parent_id", "INTEGER", True),
        ("is_transfer", "BOOLEAN", False),
        ("is_income", "BOOLEAN", False),
        ("is_sensitive", "BOOLEAN", False),
    ],
    "category_rules": [
        ("id", "INTEGER", False),
        ("pattern", "VARCHAR(100)", False),
        ("match", "VARCHAR(12)", False),
        ("priority", "INTEGER", False),
        ("category_id", "INTEGER", False),
    ],
    "transaction_categories": [
        ("id", "INTEGER", False),
        ("transaction_id", "INTEGER", False),
        ("category_id", "INTEGER", False),
        ("source", "VARCHAR(10)", False),
        ("rule_id", "INTEGER", True),
    ],
}
UNIQUES = {
    "categories": [("uq_categories_name", ["name"])],
    "category_rules": [("uq_category_rules_match_pattern", ["match", "pattern"])],
    "transaction_categories": [("uq_transaction_categories_transaction_id", ["transaction_id"])],
}
FOREIGN_KEYS = {
    "categories": [("fk_categories_parent_id_categories", ["parent_id"], "categories")],
    "category_rules": [("fk_category_rules_category_id_categories", ["category_id"], "categories")],
    "transaction_categories": [
        ("fk_transaction_categories_category_id_categories", ["category_id"], "categories"),
        ("fk_transaction_categories_rule_id_category_rules", ["rule_id"], "category_rules"),
        (
            "fk_transaction_categories_transaction_id_transactions",
            ["transaction_id"],
            "transactions",
        ),
    ],
}
TREE = {
    "Food": ("", ["Groceries", "Dining", "Coffee & Dessert"]),
    "Home": ("", ["Rent & Mortgage", "Utilities & Internet", "Home & Garden"]),
    "Transport": (
        "",
        ["Gas", "Parking & Tolls", "Public Transit", "Rideshare & Taxi", "Car Maintenance"],
    ),
    "Shopping": ("", ["General Shopping", "Clothing", "Electronics"]),
    "Subscriptions": ("", ["Subscriptions & Digital"]),
    "Health": ("sensitive", ["Medical", "Pharmacy", "Fitness"]),
    "Personal": ("", ["Personal Care", "Gifts & Donations", "Education"]),
    "Travel": ("", ["Flights", "Lodging", "Travel Other"]),
    "Entertainment": ("", ["Entertainment & Events", "Gaming"]),
    "Financial": ("", ["Fees & Interest", "Insurance", "Taxes"]),
    "Transfers": ("transfer", ["Transfer", "Credit Card Payment"]),
    "Income": ("income", ["Paycheck", "Interest Income", "Other Income"]),
}


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def at_0008(url: str) -> str:
    command.upgrade(make_config(url), "0008")
    return url


def rows(url: str, sql: str) -> list[tuple]:
    engine = get_engine(url)
    with engine.connect() as connection:
        found = [tuple(row) for row in connection.execute(text(sql)).all()]
    engine.dispose()
    return found


def test_0008_follows_0007(url: str) -> None:
    script = ScriptDirectory.from_config(make_config(url)).get_revision("0008")
    assert script.down_revision == "0007"


def test_migration_file_is_self_contained() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "finances" not in source
    assert "server_default" not in source


@pytest.mark.parametrize("table", sorted(COLUMNS))
def test_columns_keys_and_constraints(at_0008: str, table: str) -> None:
    engine = get_engine(at_0008)
    found = inspect(engine)
    columns = [
        (column["name"], str(column["type"]), column["nullable"])
        for column in found.get_columns(table)
    ]
    primary = found.get_pk_constraint(table)
    uniques = [(item["name"], item["column_names"]) for item in found.get_unique_constraints(table)]
    foreign = sorted(
        (item["name"], item["constrained_columns"], item["referred_table"])
        for item in found.get_foreign_keys(table)
    )
    engine.dispose()
    assert columns == COLUMNS[table]
    assert (primary["name"], primary["constrained_columns"]) == (f"pk_{table}", ["id"])
    assert uniques == UNIQUES[table]
    assert foreign == sorted(FOREIGN_KEYS[table])


@pytest.mark.parametrize(
    ("row_class", "table"),
    [
        (CategoryRow, "categories"),
        (CategoryRuleRow, "category_rules"),
        (TransactionCategoryRow, "transaction_categories"),
    ],
)
def test_the_orm_classes_match_the_migrated_tables(at_0008: str, row_class, table: str) -> None:
    assert row_class.__table__ is Base.metadata.tables[table]
    assert [
        (column.name, str(column.type), column.nullable) for column in row_class.__table__.columns
    ] == COLUMNS[table]


def test_the_default_tree_is_seeded(at_0008: str) -> None:
    groups = rows(
        at_0008,
        "SELECT id, name, is_transfer, is_income, is_sensitive FROM categories"
        " WHERE parent_id IS NULL ORDER BY id",
    )
    assert [name for _, name, *_ in groups] == list(TREE)
    assert [row[0] for row in groups] == list(range(1, 13))
    found = {}
    for group_id, group, *flags in groups:
        kind, _ = TREE[group]
        assert flags == [kind == "transfer", kind == "income", kind == "sensitive"]
        children = rows(
            at_0008,
            "SELECT name, is_transfer, is_income, is_sensitive FROM categories"
            f" WHERE parent_id = {group_id} ORDER BY id",
        )
        found[group] = [name for name, *_ in children]
        assert all(list(child[1:]) == flags for child in children)
    assert found == {group: names for group, (_, names) in TREE.items()}
    assert rows(at_0008, "SELECT min(id), max(id), count(*) FROM categories")[0] == (1, 46, 46)


def test_category_names_are_unique(at_0008: str) -> None:
    engine = get_engine(at_0008)
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.execute(
            text(
                "INSERT INTO categories (name, parent_id, is_transfer, is_income, is_sensitive)"
                " VALUES ('Dining', 1, 0, 0, 0)"
            )
        )
    engine.dispose()


def test_downgrade_removes_only_the_three_tables(at_0008: str) -> None:
    command.downgrade(make_config(at_0008), "0007")
    engine = get_engine(at_0008)
    names = set(inspect(engine).get_table_names())
    engine.dispose()
    assert names.isdisjoint({"categories", "category_rules", "transaction_categories"})
    assert "transactions" in names
