from datetime import date

import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account

runner = CliRunner(env={"COLUMNS": "250"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
MAY = ("--month", "2026-05")


def run(*args: object):
    return runner.invoke(app, [str(arg) for arg in args])


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]]


def table_rows(output: str) -> list[list[str]]:
    return [cells(line) for line in output.splitlines() if line.startswith(("│", "┃"))]


def plain_lines(output: str) -> list[str]:
    tables = ("│", "┃", "┏", "┡", "└")
    return [line for line in output.splitlines() if line and not line.startswith(tables)]


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
def money(migrated: Settings) -> Settings:
    """February to May 2026 on one card: dining that jumps in May, a streaming price rise, a
    second video subscription, coffee eight times in May, and an interest charge."""
    rows = [
        (date(2026, 2, 3), -6000, "ACME DINER"),
        (date(2026, 3, 17), -6000, "ACME DINER"),
        (date(2026, 4, 9), -6000, "ACME DINER"),
        (date(2026, 5, 22), -20000, "ACME DINER"),
        (date(2026, 2, 5), -1599, "QUUX STREAMING"),
        (date(2026, 3, 5), -1599, "QUUX STREAMING"),
        (date(2026, 4, 5), -1599, "QUUX STREAMING"),
        (date(2026, 5, 5), -1799, "QUUX STREAMING"),
        (date(2026, 3, 12), -999, "BAZ VIDEO"),
        (date(2026, 4, 12), -999, "BAZ VIDEO"),
        (date(2026, 5, 12), -999, "BAZ VIDEO"),
        (date(2026, 5, 28), -2345, "PURCHASE INTEREST CHARGE"),
    ] + [(date(2026, 5, day), -500, "ACME COFFEE") for day in (2, 3, 6, 9, 10, 13, 16, 17)]
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Example Card Co", "credit_card")
        for number, (day, cents, description) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=card.id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    for pattern, category in (
        ("ACME DINER", "Dining"),
        ("QUUX STREAMING", "Subscriptions & Digital"),
        ("BAZ VIDEO", "Subscriptions & Digital"),
        ("ACME COFFEE", "Coffee & Dessert"),
    ):
        assert run("rules", "add", "--pattern", pattern, "--category", category).exit_code == 0
    return migrated


@pytest.mark.parametrize("args", [("insights",), ("insights", *MAY), ("merchants", *MAY)])
def test_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run(*args)
    assert (result.exit_code, result.stderr) == (1, NOT_MIGRATED)


def test_no_findings(migrated: Settings) -> None:
    result = run("insights", *MAY)
    assert (result.exit_code, result.stdout) == (
        0,
        "Insights for 2026-05.\nNo findings.\n",
    )
    assert run("merchants", *MAY).stdout == "Merchants for 2026-05.\nNo spending.\n"


def test_the_findings_of_a_month(money: Settings) -> None:
    result = run("insights", *MAY)
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        ["Severity", "Type", "About", "Saves a month", "Detail"],
        ["high", "interest", "", "$23.45", "Interest charged: $23.45."],
        [
            "medium",
            "spike",
            "Dining",
            "$140.00",
            "Dining: $200.00 this month, against $60.00 a month before.",
        ],
        [
            "medium",
            "price_increase",
            "QUUX STREAMING",
            "$2.00",
            "QUUX STREAMING went from $15.99 to $17.99.",
        ],
        [
            "low",
            "frequent_small",
            "ACME COFFEE",
            "$20.00",
            "ACME COFFEE: 8 visits averaging $5.00.",
        ],
        [
            "low",
            "subscription_overlap",
            "Subscriptions & Digital",
            "$9.99",
            "Subscriptions & Digital: QUUX STREAMING ($17.99), BAZ VIDEO ($9.99).",
        ],
    ]
    assert plain_lines(result.stdout) == [
        "Insights for 2026-05.",
        "Findings: 5. Could save up to $195.44 a month.",
    ]


def test_the_merchants_of_a_month(money: Settings) -> None:
    result = run("merchants", *MAY)
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        ["Merchant", "Visits", "Spent", "Average", "Baseline", "Change", "Weekend"],
        ["ACME DINER", "1", "$200.00", "$200.00", "$60.00", "+$140.00", "0"],
        ["ACME COFFEE", "8", "$40.00", "$5.00", "$0.00", "+$40.00", "6"],
        ["PURCHASE INTEREST CHARGE", "1", "$23.45", "$23.45", "$0.00", "+$23.45", "0"],
        ["QUUX STREAMING", "1", "$17.99", "$17.99", "$15.99", "+$2.00", "0"],
        ["BAZ VIDEO", "1", "$9.99", "$9.99", "$6.66", "+$3.33", "0"],
    ]
    assert plain_lines(result.stdout) == ["Merchants for 2026-05."]


def test_an_earlier_month(money: Settings) -> None:
    result = run("insights", "--month", "2026-04")
    assert table_rows(result.stdout) == []
    assert plain_lines(result.stdout) == ["Insights for 2026-04.", "No findings."]
    rows = table_rows(run("merchants", "--month", "2026-04").stdout)
    assert rows[1:] == [
        ["ACME DINER", "1", "$60.00", "$60.00", "$40.00", "+$20.00", "0"],
        ["QUUX STREAMING", "1", "$15.99", "$15.99", "$10.66", "+$5.33", "1"],
        ["BAZ VIDEO", "1", "$9.99", "$9.99", "$3.33", "+$6.66", "1"],
    ]


@pytest.mark.parametrize("command", ["insights", "merchants"])
def test_a_month_that_is_not_one(money: Settings, command: str) -> None:
    result = run(command, "--month", "2026-13")
    assert failed_cleanly(result, "month must be a year and month, like 2026-05")
