from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from tests.support import CLI_NOT_MIGRATED, failed_cleanly, plain_lines, run, table_rows

HEADINGS = ["Budget", "Kind", "Target", "Spent", "Left", "Used", "Month gone"]
AMOUNT = "a budget must be an amount from $0.01 to $1,000,000.00"


@pytest.fixture
def money(tmp_settings: Settings) -> Settings:
    """May on one card: dining $300.00, groceries $120.00 less a $20.00 refund, a coffee."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (day, cents, description) in enumerate(
            (
                (5, -20000, "ACME DINER"),
                (12, -10000, "ACME DINER"),
                (6, -12000, "FOOBAR GROCERY"),
                (9, 2000, "FOOBAR GROCERY"),
                (7, -450, "ACME COFFEE"),
            ),
            start=1,
        ):
            session.add(
                TransactionRow(
                    account_id=card.id,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    for pattern, category in (
        ("ACME DINER", "Dining"),
        ("FOOBAR", "Groceries"),
        ("ACME COFFEE", "Coffee & Dessert"),
    ):
        assert run("rules", "add", "--pattern", pattern, "--category", category).exit_code == 0
    return tmp_settings


def set_budgets() -> None:
    for name, amount in (
        ("dining", "250"),
        ("Food", "$400.00"),
        ("Groceries", "200.00"),
        ("travel", "100"),
    ):
        assert run("budgets", "set", "--name", name, "--amount", amount).exit_code == 0


@pytest.mark.parametrize(
    "args",
    [("list",), ("set", "--name", "Dining", "--amount", "1"), ("remove", "--name", "Dining")],
)
def test_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run("budgets", *args)
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)


def test_set_list_and_remove(money: Settings) -> None:
    assert run("budgets", "list", "--month", "2026-05").stdout == (
        "Budgets for 2026-05.\nNo budgets.\n"
    )
    result = run("budgets", "set", "--name", "dining", "--amount", "250")
    assert (result.exit_code, result.stdout) == (0, 'Budget for "Dining": $250.00 a month.\n')
    set_budgets()
    result = run("budgets", "list", "--month", "2026-05")
    assert table_rows(result.stdout) == [
        HEADINGS,
        ["Dining", "category", "$250.00", "$300.00", "-$50.00", "120%", "100%"],
        ["Food", "group", "$400.00", "$404.50", "-$4.50", "101%", "100%"],
        ["Groceries", "category", "$200.00", "$100.00", "$100.00", "50%", "100%"],
        ["Travel", "group", "$100.00", "$0.00", "$100.00", "0%", "100%"],
    ]
    assert plain_lines(result.stdout) == ["Budgets for 2026-05.", "Over budget: 2."]
    result = run("budgets", "set", "--name", "Dining", "--amount", "350")
    assert result.stdout == 'Budget for "Dining": $350.00 a month.\n'
    result = run("budgets", "remove", "--name", "groceries")
    assert (result.exit_code, result.stdout) == (0, 'Removed the budget for "Groceries".\n')
    rows = table_rows(run("budgets", "list", "--month", "2026-05").stdout)
    assert [row[:3] for row in rows[1:]] == [
        ["Dining", "category", "$350.00"],
        ["Food", "group", "$400.00"],
        ["Travel", "group", "$100.00"],
    ]


def test_over_budget_is_a_finding(money: Settings) -> None:
    set_budgets()
    rows = table_rows(run("insights", "--month", "2026-05").stdout)
    assert rows[1:] == [
        [
            "medium",
            "over_budget",
            "Dining",
            "$50.00",
            "Dining: $300.00 spent against a budget of $250.00.",
        ],
        [
            "medium",
            "over_budget",
            "Food",
            "$4.50",
            "Food: $404.50 spent against a budget of $400.00.",
        ],
    ]


def test_deleting_a_category_removes_its_budget(money: Settings) -> None:
    set_budgets()
    result = run("categories", "delete", "--name", "Groceries", "--move-to", "Dining")
    assert result.exit_code == 0
    rows = table_rows(run("budgets", "list", "--month", "2026-05").stdout)
    assert [row[0] for row in rows[1:]] == ["Dining", "Food", "Travel"]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("set", "--name", "Nope", "--amount", "10"), "category not found"),
        (("set", "--name", "Dining", "--amount", "0"), AMOUNT),
        (("set", "--name", "Dining", "--amount", "-5"), AMOUNT),
        (("set", "--name", "Dining", "--amount", "ten"), AMOUNT),
        (("set", "--name", "Dining", "--amount", "1000000.01"), AMOUNT),
        (("remove", "--name", "Nope"), "category not found"),
        (("remove", "--name", "Dining"), "there is no budget for Dining"),
        (("list", "--month", "2026-13"), "month must be a year and month, like 2026-05"),
    ],
)
def test_a_refused_command(money: Settings, args, message: str) -> None:
    assert failed_cleanly(run("budgets", *args), message)
