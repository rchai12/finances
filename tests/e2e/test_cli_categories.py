from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account

runner = CliRunner(env={"COLUMNS": "200"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
GROUP_GIVEN = "rules and transactions take a category, not a group"
LINE = "Categorized {} transactions: {} changed, {} without a category.\n"


def run(*args: object):
    return runner.invoke(app, [str(arg) for arg in args])


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]]


def table_rows(output: str) -> list[list[str]]:
    return [cells(line) for line in output.splitlines() if line.startswith(("│", "┃"))]


def failed_cleanly(result, message: str) -> bool:
    return (
        result.exit_code == 1
        and isinstance(result.exception, SystemExit)
        and result.stderr == f"Error: {message}\n"
        and result.stdout == ""
    )


@pytest.fixture
def migrated(tmp_settings: Settings) -> Settings:
    assert run("db", "upgrade").exit_code == 0
    return tmp_settings


@pytest.fixture
def spending(migrated: Settings) -> Settings:
    """Transactions 1 to 4, posted on 1 to 4 May 2026 in this order."""
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card", last4="9999")
        for day, cents, description in (
            (1, -450, "SQ *ACME COFFEE"),
            (2, -500, "ACME COFFEE #12"),
            (3, -2599, "FOOBAR GROCERY #77 DECATUR GA"),
            (4, 300000, "PAYCHECK EXAMPLE CORP"),
        ):
            session.add(
                TransactionRow(
                    account_id=card.id,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{day}".ljust(64, "0"),
                )
            )
    engine.dispose()
    return migrated


@pytest.mark.parametrize(
    "args",
    [
        ("categories", "list"),
        ("categories", "add", "--name", "X", "--group", "Food"),
        ("rules", "list"),
        ("rules", "add", "--pattern", "X", "--category", "Dining"),
        ("rules", "delete", "--id", "1"),
        ("categorize",),
        ("uncategorized",),
        ("transactions", "set-category", "--id", "1", "--clear"),
    ],
)
def test_every_command_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run(*args)
    assert (result.exit_code, result.stderr) == (1, NOT_MIGRATED)


# Categories


def test_the_default_categories(migrated: Settings) -> None:
    rows = table_rows(run("categories", "list").stdout)
    assert rows[0] == ["Group", "Category", "Kind"]
    assert len(rows) == 35
    assert rows[1:3] == [
        ["Entertainment", "Entertainment & Events", ""],
        ["Entertainment", "Gaming", ""],
    ]
    assert ["Health", "Fitness", "sensitive"] in rows
    assert ["Transfers", "Credit Card Payment", "transfer"] in rows
    assert ["Income", "Interest Income", "income"] in rows
    groups = [row[0] for row in rows[1:]]
    assert groups == sorted(groups, key=str.lower)
    assert [row[1] for row in rows if row[0] == "Food"] == [
        "Coffee & Dessert",
        "Dining",
        "Groceries",
    ]


def test_add_a_category_to_a_group(migrated: Settings) -> None:
    result = run("categories", "add", "--name", "  Therapy ", "--group", "health")
    assert (result.exit_code, result.stdout) == (0, 'Added category "Therapy" to Health.\n')
    assert ["Health", "Therapy", "sensitive"] in table_rows(run("categories", "list").stdout)


@pytest.mark.parametrize(
    ("name", "group", "message"),
    [
        ("Therapy", "Nope", "group not found"),
        ("Therapy", "Dining", "group not found"),
        ("dining", "Food", "a category with this name already exists"),
        ("food", "Food", "a category with this name already exists"),
        ("  ", "Food", "a category name must be 1 to 50 characters"),
        ("N" * 51, "Food", "a category name must be 1 to 50 characters"),
    ],
)
def test_a_refused_category(migrated: Settings, name: str, group: str, message: str) -> None:
    assert failed_cleanly(run("categories", "add", "--name", name, "--group", group), message)


# Rules and categorizing


def test_rules_categorize_past_transactions(spending: Settings) -> None:
    result = run("rules", "add", "--pattern", "acme  coffee", "--category", "coffee & dessert")
    assert (result.exit_code, result.stdout) == (
        0,
        'Added rule 1: contains "ACME COFFEE" -> Coffee & Dessert.\n' + LINE.format(4, 2, 2),
    )
    result = run(
        "rules",
        "add",
        "--pattern",
        "ACME",
        "--match",
        "starts_with",
        "--priority",
        "5",
        "--category",
        "Dining",
    )
    assert result.stdout == 'Added rule 2: starts_with "ACME" -> Dining.\n' + LINE.format(4, 2, 2)
    assert table_rows(run("rules", "list").stdout) == [
        ["ID", "Priority", "Match", "Pattern", "Category"],
        ["2", "5", "starts_with", "ACME", "Dining"],
        ["1", "0", "contains", "ACME COFFEE", "Coffee & Dessert"],
    ]
    result = run("rules", "delete", "--id", "2")
    assert (result.exit_code, result.stdout) == (0, "Deleted rule 2.\n" + LINE.format(4, 2, 2))
    assert run("categorize").stdout == LINE.format(4, 0, 2)


def test_uncategorized_transactions(spending: Settings) -> None:
    headings = ["ID", "Date", "Account", "Merchant", "Amount"]
    assert table_rows(run("uncategorized").stdout) == [
        headings,
        ["4", "2026-05-04", "Test Card", "PAYCHECK EXAMPLE CORP", "$3,000.00"],
        ["3", "2026-05-03", "Test Card", "FOOBAR GROCERY", "-$25.99"],
        ["2", "2026-05-02", "Test Card", "ACME COFFEE", "-$5.00"],
        ["1", "2026-05-01", "Test Card", "ACME COFFEE", "-$4.50"],
    ]
    assert table_rows(run("uncategorized", "--limit", "1").stdout)[1:] == [
        ["4", "2026-05-04", "Test Card", "PAYCHECK EXAMPLE CORP", "$3,000.00"]
    ]
    run("rules", "add", "--pattern", "ACME COFFEE", "--category", "Dining")
    assert [row[0] for row in table_rows(run("uncategorized").stdout)[1:]] == ["4", "3"]
    run("rules", "add", "--pattern", "FOOBAR", "--category", "Groceries")
    run("rules", "add", "--pattern", "PAYCHECK", "--category", "Paycheck")
    assert run("uncategorized").stdout == "No uncategorized transactions.\n"
    assert run("uncategorized", "--limit", "0").exit_code == 2
    assert run("uncategorized", "--limit", "1001").exit_code == 2


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--pattern", "X", "--category", "Nope"), "category not found"),
        (("--pattern", "X", "--category", "Food"), GROUP_GIVEN),
        (
            ("--pattern", "X", "--category", "Dining", "--match", "regex"),
            "match must be one of: contains, starts_with, equals",
        ),
        (
            ("--pattern", "   ", "--category", "Dining"),
            "a rule pattern must be 1 to 100 characters",
        ),
        (
            ("--pattern", "P" * 101, "--category", "Dining"),
            "a rule pattern must be 1 to 100 characters",
        ),
    ],
)
def test_a_refused_rule(spending: Settings, args, message: str) -> None:
    assert failed_cleanly(run("rules", "add", *args), message)
    assert run("rules", "list").stdout == "No rules.\n"


def test_the_same_rule_twice_is_refused(spending: Settings) -> None:
    run("rules", "add", "--pattern", "ACME", "--category", "Dining")
    result = run("rules", "add", "--pattern", "acme", "--category", "Groceries")
    assert failed_cleanly(result, "a rule with this pattern and match already exists")
    assert (
        run(
            "rules", "add", "--pattern", "acme", "--match", "equals", "--category", "Groceries"
        ).exit_code
        == 0
    )


def test_deleting_an_unknown_rule(spending: Settings) -> None:
    assert failed_cleanly(run("rules", "delete", "--id", "9"), "rule not found")


# Setting a category by hand


def test_a_category_set_by_hand_is_kept(spending: Settings) -> None:
    result = run("transactions", "set-category", "--id", "3", "--category", "groceries")
    assert (result.exit_code, result.stdout) == (0, "Transaction 3: Groceries, set by hand.\n")
    run("rules", "add", "--pattern", "ACME COFFEE", "--category", "Coffee & Dessert")
    assert run("categorize").stdout == LINE.format(4, 0, 1)
    result = run("rules", "add", "--pattern", "FOOBAR", "--category", "Dining")
    assert result.stdout == 'Added rule 2: contains "FOOBAR" -> Dining.\n' + LINE.format(4, 0, 1)
    result = run("transactions", "set-category", "--id", "3", "--clear")
    assert (result.exit_code, result.stdout) == (
        0,
        "Transaction 3: category left to the rules.\n" + LINE.format(4, 1, 1),
    )


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--id", "99", "--category", "Dining"), "transaction not found"),
        (("--id", "99", "--clear"), "transaction not found"),
        (("--id", "1", "--category", "Nope"), "category not found"),
        (("--id", "1", "--category", "Food"), GROUP_GIVEN),
        (("--id", "1"), "give either --category or --clear"),
        (("--id", "1", "--category", "Dining", "--clear"), "give either --category or --clear"),
    ],
)
def test_a_refused_category_by_hand(spending: Settings, args, message: str) -> None:
    assert failed_cleanly(run("transactions", "set-category", *args), message)


def test_one_transaction_is_counted_in_the_singular(migrated: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        session.add(
            TransactionRow(
                account_id=card.id,
                posted_date=date(2026, 5, 1),
                amount_cents=-450,
                description="ACME COFFEE",
                source="statement",
                fingerprint="x".ljust(64, "0"),
            )
        )
    engine.dispose()
    assert (
        run("categorize").stdout == "Categorized 1 transaction: 0 changed, 1 without a category.\n"
    )


# New transactions are categorized as they arrive


def test_an_import_categorizes_quietly(
    migrated: Settings, fake_bank, fake_statement_pdf, tmp_path: Path
) -> None:
    details = ["--institution", "Fake Bank", "--type", "credit_card", "--last4", "1111"]
    assert run("accounts", "add", "--name", "Fake Card", *details).exit_code == 0
    run("rules", "add", "--pattern", "ACME COFFEE", "--category", "Coffee & Dessert")
    path = tmp_path / "statement.pdf"
    path.write_bytes(fake_statement_pdf())
    result = run("import", "statement", path)
    assert result.exit_code == 0
    assert "Categorized" not in result.stdout
    merchants = [row[3] for row in table_rows(run("uncategorized").stdout)[1:]]
    assert sorted(merchants) == ["FOOBAR GROCERY", "PAYMENT THANK YOU"]
